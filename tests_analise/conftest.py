"""Fixtures compartilhadas pelos testes do motor de análise."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analise import market  # noqa: E402


class RespostaFalsa:
    """Imita o objeto devolvido por requests.get."""

    def __init__(self, corpo, status=200):
        self._corpo = corpo
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._corpo


@pytest.fixture
def dados_temp(tmp_path, monkeypatch):
    """Aponta PORTFOLIO_DATA_DIR para um diretório temporário."""
    monkeypatch.setenv("PORTFOLIO_DATA_DIR", str(tmp_path))
    (tmp_path / "history").mkdir(parents=True, exist_ok=True)
    market.limpar_cache()
    return tmp_path


@pytest.fixture
def rede(monkeypatch):
    """Substitui requests.get por uma tabela de rotas: trecho da URL -> resposta."""
    rotas: dict = {}
    chamadas: list = []

    def falso_get(url, params=None, headers=None, timeout=None):
        chamadas.append({"url": url, "params": params or {}})
        for trecho, resposta in rotas.items():
            if trecho in url:
                valor = resposta(url, params) if callable(resposta) else resposta
                if isinstance(valor, Exception):
                    raise valor
                return valor
        raise AssertionError(f"URL nao mapeada no teste: {url}")

    monkeypatch.setattr(market.requests, "get", falso_get)
    return type("Rede", (), {"rotas": rotas, "chamadas": chamadas})()


def chart_yahoo(preco, anterior, nome="Fundo"):
    """Resposta da chart API do Yahoo."""
    return RespostaFalsa(
        {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "regularMarketPrice": preco,
                            "chartPreviousClose": anterior,
                            "longName": nome,
                            "currency": "BRL",
                        }
                    }
                ]
            }
        }
    )


@pytest.fixture
def mercado_padrao(rede):
    """Indicadores macro estáveis; cada teste acrescenta as cotações que quiser."""
    rede.rotas.update(
        {
            "bcdata.sgs.4389": RespostaFalsa([{"data": "01/09/2026", "valor": "15,00"}]),
            "bcdata.sgs.432": RespostaFalsa([{"data": "01/09/2026", "valor": "15,00"}]),
            "bcdata.sgs.433": RespostaFalsa([{"valor": "0,40"}]),
            "%5EBVSP": RespostaFalsa({"chart": {"result": []}}),
            "^BVSP": RespostaFalsa({"chart": {"result": []}}),
            "^IFIX": RespostaFalsa({"chart": {"result": []}}),
        }
    )
    return rede


@pytest.fixture
def snapshot_exemplo():
    """Snapshot mínimo para exercitar relatório, fundamentos e prompt."""
    return {
        "gerado_em": "2026-09-01T10:30:00",
        "data": "2026-09-01",
        "perfil": "Renda mensal com risco moderado.",
        "totais": {
            "valor_investido": 20000.0,
            "valor_atual": 22000.0,
            "resultado": 2000.0,
            "resultado_pct": 10.0,
            "resultado_dia": 35.5,
            "posicoes": 2,
        },
        "classes": {
            "fii": {
                "rotulo": "FIIs",
                "posicoes": 1,
                "valor_investido": 10000.0,
                "valor_atual": 12000.0,
                "resultado": 2000.0,
                "resultado_pct": 20.0,
                "peso_pct": 54.55,
            },
            "cdb": {
                "rotulo": "CDBs",
                "posicoes": 1,
                "valor_investido": 10000.0,
                "valor_atual": 10000.0,
                "resultado": 0.0,
                "resultado_pct": 0.0,
                "peso_pct": 45.45,
            },
        },
        "posicoes": [
            {
                "id": "a1",
                "tipo": "fii",
                "descricao": "MXRF11",
                "ticker": "MXRF11",
                "nome": "Maxi Renda",
                "quantidade": 1000.0,
                "preco_medio": 10.0,
                "preco_atual": 12.0,
                "valor_investido": 10000.0,
                "valor_atual": 12000.0,
                "resultado": 2000.0,
                "resultado_pct": 20.0,
                "variacao_dia_pct": 0.3,
                "resultado_dia": 35.5,
                "peso_pct": 54.55,
                "observacao": "",
                "erro_cotacao": None,
            },
            {
                "id": "b2",
                "tipo": "cdb",
                "descricao": "CDB Inter 110% do CDI",
                "banco": "Inter",
                "indexador": "CDI",
                "taxa": 110.0,
                "rotulo_taxa": "110% do CDI",
                "data_aplicacao": "2025-01-02",
                "data_vencimento": "2027-01-04",
                "valor_investido": 10000.0,
                "valor_atual": 10000.0,
                "valor_liquido": 9800.0,
                "resultado": 0.0,
                "resultado_pct": 0.0,
                "dias_para_vencer": 490,
                "vencido": False,
                "peso_pct": 45.45,
                "observacao": "",
                "aviso": None,
            },
        ],
        "limite_concentracao_pct": 25.0,
        "emissores_renda_fixa": [
            {
                "nome": "Inter",
                "valor": 10000.0,
                "peso_pct": 45.45,
                "fgc_limite": 250000.0,
                "fgc_uso_pct": 4.0,
                "acima_do_fgc": False,
            }
        ],
        "alertas": [
            {
                "severidade": "atencao",
                "titulo": "Concentracao em MXRF11: 54.5%",
                "descricao": "A posicao representa 54.5% da carteira.",
                "alvo": "MXRF11",
                "origem": "calculo",
            }
        ],
        "saude_carteira": "boa",
        "destaques": {"melhores": [], "piores": []},
        "macro": {
            "cdi_anual_pct": {"valor": 14.9, "fonte": "BCB/SGS 4389"},
            "selic_meta_pct": {"valor": 15.0, "fonte": "BCB/SGS 432"},
            "ipca_12m_pct": {"valor": 4.2, "fonte": "BCB/SGS 433"},
            "indices": {"ibovespa": {"valor": 145200.5, "variacao_dia_pct": 0.42}},
            "consultado_em": "2026-09-01T10:29:00",
        },
    }


@pytest.fixture
def ia_exemplo():
    """Resposta da IA no formato do schema."""
    return {
        "resumo": "Carteira concentrada em um FII de papel, com um CDB no CDI.",
        "saude_carteira": "boa",
        "ativos": [
            {
                "ticker": "MXRF11",
                "nome": "Maxi Renda FII",
                "classificacao": "papel",
                "segmento": "Recebíveis",
                "gestora": "XP Asset",
                "p_vp": 0.98,
                "dy_12m_pct": 12.4,
                "patrimonio": "R$ 7,57 bi",
                "vacancia_pct": None,
                "comentario": "Fundo de papel com carteira pulverizada de CRIs.",
                "risco": "Sensibilidade à inadimplência dos devedores.",
                "fonte": "Relatório gerencial",
            }
        ],
        "carteira": {
            "diversificacao": "Dividida entre renda variável e renda fixa.",
            "concentracao_setorial": "Exposição única a recebíveis.",
            "concentracao_gestor": "Um único gestor na parte de FIIs.",
            "valuation": "Negociado próximo ao valor patrimonial.",
            "renda": "Yield acima do CDI corrente.",
            "conclusao": "Carteira simples, com concentração relevante.",
        },
        "riscos": [
            {
                "titulo": "Concentração em um único FII",
                "descricao": "Mais da metade do patrimônio em um ativo.",
                "severidade": "atencao",
                "ativos": ["MXRF11"],
            }
        ],
        "fatos": [
            {
                "ativo": "MXRF11",
                "titulo": "Distribuição mantida",
                "descricao": "Provento estável no último mês.",
                "severidade": "info",
                "fonte": "Comunicado ao mercado",
            }
        ],
        "oportunidades": [
            {
                "tipo": "rebalanceamento",
                "titulo": "Diluir a concentração",
                "descricao": "Aportes em outros segmentos reduziriam o risco.",
                "ativos": ["MXRF11"],
            }
        ],
        "contexto_mercado": "Selic elevada pressiona os múltiplos dos FIIs.",
        "_meta": {
            "modelo": "claude-opus-5",
            "effort": "medium",
            "tokens_entrada": 1200,
            "tokens_saida": 3400,
            "buscas_web": 6,
            "gerado_em": "2026-09-01T10:30:00",
        },
    }
