"""
Shelly Service Module - Integração com os dispositivos Shelly (HTTP)
"""
import os
import requests
import logging

logger = logging.getLogger(__name__)

# Lê IPs dos dispositivos a partir de variáveis de ambiente
SHELLY_SOLAR_IP = os.getenv('SHELLY_SOLAR_IP', '192.168.188.25')
SHELLY_HOUSE_IP = os.getenv('SHELLY_HOUSE_IP', '192.168.188.5')
TIMEOUT_HTTP = 1.5


def fetch_shelly_solar():
    """
    Busca a potência AC do painel solar (Shelly Gen2 ou Gen1)
    Retorna o valor em Watts, ou 0.0 se falhar
    """
    try:
        # Tentativa 1: Gen2 RPC API
        url = f"http://{SHELLY_SOLAR_IP}/rpc/Shelly.GetStatus"
        res = requests.get(url, timeout=TIMEOUT_HTTP)
        if res.status_code == 200:
            data = res.json()
            if 'pm1:0' in data and 'apower' in data['pm1:0']:
                return float(data['pm1:0']['apower'])
            if 'switch:0' in data and 'apower' in data['switch:0']:
                return float(data['switch:0']['apower'])
    except Exception as e:
        logger.debug(f"Tentativa Gen2 falhada para Shelly Solar: {str(e)}")

    try:
        # Tentativa 2: Gen1 Status API
        url = f"http://{SHELLY_SOLAR_IP}/status"
        res = requests.get(url, timeout=TIMEOUT_HTTP)
        if res.status_code == 200:
            data = res.json()
            if 'meters' in data and len(data['meters']) > 0:
                return float(data['meters'][0]['power'])
    except Exception as e:
        logger.debug(f"Tentativa Gen1 falhada para Shelly Solar: {str(e)}")

    return 0.0


def fetch_shelly_house():
    """
    Busca a potência de troca com a rede elétrica (importação/exportação)
    se valor e negativo = exportando para a rede, se positivo = importando da rede
    Retorna o valor em Watts, ou 0.0 se falhar
    """
    try:
        url = f"http://{SHELLY_HOUSE_IP}/status"
        res = requests.get(url, timeout=TIMEOUT_HTTP)
        if res.status_code == 200:
            data = res.json()
            if 'emeters' in data:
                total = sum(float(m.get('power', 0.0)) for m in data['emeters'])
                return total
    except Exception as e:
        logger.debug(f"Erro ao buscar dados da Shelly Casa: {str(e)}")

    return 0.0
