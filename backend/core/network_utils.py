"""
Utilitários de rede para manipulação e validação de IPs, faixas (ranges) e CIDR.
Reutiliza os padrões robustos do ecossistema Scan Bot.
"""

import ipaddress
import re
from typing import List, Set


def is_valid_ipv4(ip_str: str) -> bool:
    """Valida se uma string é um endereço IPv4 válido."""
    try:
        ip = ipaddress.IPv4Address(ip_str.strip())
        return not ip.is_multicast and not ip.is_loopback
    except (ipaddress.AddressValueError, ValueError):
        return False


def parse_ip_targets(raw_input: str) -> List[str]:
    """
    Interpreta diferentes formatos de entrada de alvos de rede e retorna
    uma lista de IPs únicos ordenada.
    
    Formatos suportados:
    - IP único: "192.168.1.10"
    - Lista separada por vírgula ou espaço: "192.168.1.10, 192.168.1.15; 192.168.1.20"
    - Faixa de IPs (range): "192.168.1.100-110" ou "192.168.1.100-192.168.1.110"
    - Notação CIDR: "192.168.1.0/24"
    """
    if not raw_input or not raw_input.strip():
        return []

    # Normaliza separadores (substitui vírgulas, pontos e vírgulas e quebras de linha por espaços)
    cleaned = re.sub(r"[,;\n\r\t]+", " ", raw_input.strip())
    tokens = [t.strip() for t in cleaned.split(" ") if t.strip()]

    ips: Set[str] = set()

    for token in tokens:
        # 1. CIDR: ex 192.168.1.0/24
        if "/" in token:
            try:
                network = ipaddress.IPv4Network(token, strict=False)
                # Limita redes muito grandes para evitar travamento acidental (máx /20 = 4096 hosts)
                if network.num_addresses > 4096:
                    continue
                for host in network.hosts():
                    ips.add(str(host))
            except ValueError:
                pass
            continue

        # 2. Faixa (Range): ex 192.168.1.100-110 ou 192.168.1.100-192.168.1.110
        if "-" in token:
            range_match = re.match(r"^(\d+\.\d+\.\d+\.\d+)-(\d+\.\d+\.\d+\.\d+|\d+)$", token)
            if range_match:
                start_ip_str, end_part = range_match.groups()
                try:
                    start_ip = ipaddress.IPv4Address(start_ip_str)
                    if "." in end_part:
                        end_ip = ipaddress.IPv4Address(end_part)
                    else:
                        # Sufixo do último octeto: 192.168.1.100-110 -> 192.168.1.110
                        octets = start_ip_str.split(".")
                        octets[3] = end_part
                        end_ip = ipaddress.IPv4Address(".".join(octets))

                    if int(start_ip) <= int(end_ip):
                        # Limite de segurança de 1024 IPs por faixa
                        count = int(end_ip) - int(start_ip) + 1
                        if count <= 1024:
                            for ip_int in range(int(start_ip), int(end_ip) + 1):
                                ips.add(str(ipaddress.IPv4Address(ip_int)))
                except ValueError:
                    pass
            continue

        # 3. IP Único
        if is_valid_ipv4(token):
            ips.add(token)

    # Ordena os IPs numericamente
    return sorted(list(ips), key=lambda x: [int(octet) for octet in x.split(".")])


def get_default_local_subnet() -> str:
    """
    Identifica o endereço IP local da máquina e sugere a sub-rede /24 correspondente.
    Exemplo: se o IP da máquina for 192.168.3.179, retorna '192.168.3.0/24'.
    Em caso de falha de detecção, retorna '192.168.1.0/24'.
    """
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        octets = local_ip.split(".")
        if len(octets) == 4:
            return f"{octets[0]}.{octets[1]}.{octets[2]}.0/24"
    except Exception:
        pass
    return "192.168.1.0/24"
