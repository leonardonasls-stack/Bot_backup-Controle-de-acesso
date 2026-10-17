"""
Scanner de rede assíncrono para descoberta de terminais Control iD / iDFace.
Varre sub-redes, faixas ou listas de IPs com controle de concorrência e callback de progresso.
"""

import asyncio
from typing import List, Callable, Optional
from backend.models.device import ControlIdDevice
from backend.core.network_utils import parse_ip_targets
from backend.core.detector import probe_controlid_device


class NetworkScanner:
    """Scanner concorrente assíncrono para terminais Control iD."""

    def __init__(self, max_concurrency: int = 50, timeout: float = 2.0):
        self.max_concurrency = max_concurrency
        self.timeout = timeout
        self._is_cancelled = False

    def cancel(self):
        """Interrompe a varredura em andamento."""
        self._is_cancelled = True

    async def scan(
        self,
        targets_input: str,
        ports: Optional[List[int]] = None,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        on_device_found: Optional[Callable[[ControlIdDevice], None]] = None,
    ) -> List[ControlIdDevice]:
        """
        Executa a varredura nos alvos especificados.
        
        Args:
            targets_input: String contendo IPs, faixas ou CIDR
            ports: Lista de portas HTTP a testar (padrão: [80, 443])
            on_progress: Callback (processados, total, ip_atual)
            on_device_found: Callback acionado imediatamente ao encontrar um dispositivo
        """
        self._is_cancelled = False
        if ports is None:
            ports = [80, 443]

        ips = parse_ip_targets(targets_input)
        if not ips:
            return []

        total_checks = len(ips) * len(ports)
        processed = 0
        found_devices: List[ControlIdDevice] = []
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def check_target(ip: str, port: int):
            nonlocal processed
            if self._is_cancelled:
                return

            async with semaphore:
                if self._is_cancelled:
                    return
                dev = await probe_controlid_device(ip, port=port, timeout=self.timeout)
                processed += 1
                if on_progress:
                    on_progress(processed, total_checks, ip)
                if dev:
                    # Evita duplicar se já achou o mesmo IP na porta anterior
                    if not any(d.ip == dev.ip for d in found_devices):
                        found_devices.append(dev)
                        if on_device_found:
                            on_device_found(dev)

        tasks = []
        for ip in ips:
            for port in ports:
                tasks.append(check_target(ip, port))

        await asyncio.gather(*tasks, return_exceptions=True)
        return found_devices
