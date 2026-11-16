"""
Backend de cache em arquivo com reserva atômica.

O rate limit do formulário de contato reserva a vaga do IP com
``cache.add()``, que só grava se a chave ainda não existir. No
``FileBasedCache`` do Django esse ``add()`` faz ``has_key()`` e depois
``set()``, sem trava: pedidos simultâneos veem a chave ausente e todos
reservam. Este backend serializa as reservas com uma trava exclusiva de
arquivo, que vale entre threads e entre os processos do gunicorn.
"""

import os
from typing import Any

from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.cache.backends.filebased import FileBasedCache
from django.core.files import locks

# Fora do padrão *.djcache do FileBasedCache: o _cull() e o clear() não apagam
# a trava, e ela não conta como entrada do cache.
NOME_ARQUIVO_TRAVA = "reserva.lock"


class CacheArquivoAtomico(FileBasedCache):
    """
    ``FileBasedCache`` cujo ``add()`` é atômico entre threads e processos.

    Só o ``add()`` passa pela trava; ``get()``, ``set()`` e ``delete()``
    seguem como no Django. Uma trava única para a pasta basta: as reservas
    são raras (uma por envio do formulário) e cada uma dura milissegundos.

    Attributes:
        caminho_trava (str): Arquivo da pasta do cache usado como trava
            exclusiva das reservas.
    """

    def __init__(self, dir: str, params: dict[str, Any]) -> None:
        """
        Inicializa o cache e guarda o caminho do arquivo de trava.

        Args:
            dir (str): Pasta do cache (o ``LOCATION`` do ``CACHES``).
            params (dict[str, Any]): Demais opções do ``CACHES``.
        """
        super().__init__(dir, params)
        self._pasta = os.path.abspath(dir)
        self.caminho_trava = os.path.join(self._pasta, NOME_ARQUIVO_TRAVA)

    def add(
        self,
        key: Any,
        value: Any,
        timeout: float | None = DEFAULT_TIMEOUT,
        version: int | None = None,
    ) -> bool:
        """
        Grava a chave só se ela ainda não existir, sem corrida entre pedidos.

        A verificação e a gravação do ``add()`` herdado rodam dentro da trava
        exclusiva: enquanto um pedido reserva, os outros esperam e depois
        encontram a chave gravada.

        Args:
            key (Any): Chave do cache.
            value (Any): Valor a gravar.
            timeout (float | None): Validade em segundos; ``None`` não expira.
                Padrão: o ``TIMEOUT`` do ``CACHES``.
            version (int | None): Versão da chave. Padrão: a do ``CACHES``.

        Returns:
            bool: ``True`` se gravou (a vaga era livre), ``False`` se a chave
                já existia e não expirou.
        """
        # A pasta pode ter sido apagada desde a inicialização (o FileBasedCache
        # também recria antes de gravar).
        os.makedirs(self._pasta, exist_ok=True)
        with open(self.caminho_trava, "ab") as trava:
            locks.lock(trava, locks.LOCK_EX)
            try:
                return super().add(key, value, timeout, version)
            finally:
                locks.unlock(trava)
