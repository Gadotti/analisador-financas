"""Orquestração, persistência e o script isolado de linha de comando."""

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

from analise import ai_insights, portfolio, runner
from conftest import chart_yahoo

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "scripts" / "analisar.py"

CARTEIRA_UM_FII = {
    "versao": 2,
    "perfil": "teste",
    "posicoes": [
        {
            "id": "a1",
            "tipo": "fii",
            "ticker": "MXRF11",
            "quantidade": 1000.0,
            "preco_medio": 10.0,
            "observacao": "",
            "data_compra": None,
        }
    ],
    "config": {},
}


@pytest.fixture
def carteira(dados_temp):
    (dados_temp / "portfolio.json").write_text(
        json.dumps(CARTEIRA_UM_FII), encoding="utf-8"
    )
    return dados_temp


@pytest.fixture
def mercado(mercado_padrao):
    mercado_padrao.rotas["MXRF11.SA"] = chart_yahoo(12, 11.9, "Maxi Renda")
    return mercado_padrao


# ─────────────────────────────────────────────
# portfolio (leitura)
# ─────────────────────────────────────────────


def test_carteira_inexistente_devolve_vazia(dados_temp):
    carteira = portfolio.load()

    assert carteira["posicoes"] == []
    assert carteira["config"]["limite_fgc"] == 250000
    assert not (dados_temp / "portfolio.json").exists(), "a leitura não cria arquivo"


def test_config_completada_com_os_padroes(dados_temp):
    (dados_temp / "portfolio.json").write_text(
        json.dumps({"versao": 2, "posicoes": [], "config": {"max_fatos": 2}}), encoding="utf-8"
    )
    carteira = portfolio.load()

    assert carteira["config"]["max_fatos"] == 2
    assert carteira["config"]["alerta_prejuizo_pct"] == 15
    assert carteira["perfil"] == ""


def test_carteira_corrompida_erra_com_clareza(dados_temp):
    (dados_temp / "portfolio.json").write_text("{ nao é json", encoding="utf-8")

    with pytest.raises(portfolio.CarteiraError, match="Carteira corrompida"):
        portfolio.load()


def test_tickers_unicos_de_renda_variavel():
    carteira = {
        "posicoes": [
            {"tipo": "fii", "ticker": "MXRF11"},
            {"tipo": "cdb", "banco": "Inter"},
            {"tipo": "acao", "ticker": "PETR4"},
            {"tipo": "fii", "ticker": "MXRF11"},
        ]
    }
    assert portfolio.tickers(carteira) == ["MXRF11", "PETR4"]


# ─────────────────────────────────────────────
# runner
# ─────────────────────────────────────────────


def test_executa_a_parte_deterministica_sem_ia(carteira, mercado):
    resultado = runner.executar(usar_ia=False)

    assert resultado["ia"] is None
    assert resultado["ia_erro"] is None
    assert resultado["ia_solicitada"] is False
    assert resultado["fundamentos"] is None
    assert resultado["snapshot"]["totais"]["valor_atual"] == 12000


def test_usa_o_analisador_injetado_e_cruza_fundamentos(carteira, mercado, ia_exemplo):
    recebido = {}

    def analisador(snapshot, config):
        recebido["snapshot"] = snapshot
        recebido["config"] = config
        return ia_exemplo

    resultado = runner.executar(analisar_com_ia=analisador)

    assert recebido["snapshot"]["posicoes"]
    assert recebido["config"]["max_fatos"] == portfolio.CONFIG_PADRAO["max_fatos"]
    assert resultado["ia"] is ia_exemplo
    assert resultado["ia_erro"] is None
    assert len(resultado["fundamentos"]["fichas"]) == 1
    assert resultado["fundamentos"]["metricas"]["p_vp_medio"] == 0.98


def test_falha_da_ia_nao_derruba_o_relatorio(carteira, mercado):
    def analisador(_snapshot, _config):
        raise ai_insights.IAIndisponivel("sem crédito na conta")

    resultado = runner.executar(analisar_com_ia=analisador)

    assert resultado["ia"] is None
    assert resultado["ia_erro"] == "sem crédito na conta"
    assert resultado["snapshot"]["totais"]["valor_atual"] > 0


def test_falha_inesperada_recebe_rotulo_proprio(carteira, mercado):
    def analisador(_snapshot, _config):
        raise TypeError("objeto sem atributo")

    resultado = runner.executar(analisar_com_ia=analisador)

    assert "Falha inesperada na analise por IA" in resultado["ia_erro"]


def test_carteira_vazia_nao_chama_a_ia(dados_temp, mercado_padrao):
    chamou = []

    resultado = runner.executar(analisar_com_ia=lambda *_: chamou.append(True))

    assert chamou == []
    assert resultado["ia_erro"] == "Carteira vazia — nada a analisar."


def test_persiste_ultima_analise_e_historico(carteira, mercado):
    resultado = runner.executar(usar_ia=False)
    data = resultado["snapshot"]["data"]

    assert (carteira / "last_analysis.json").exists()
    assert (carteira / "history" / f"{data}.json").exists()
    assert runner.ultima_analise()["snapshot"]["totais"]["valor_atual"] == 12000


def test_nao_salvar_deixa_o_historico_intocado(carteira, mercado):
    runner.executar(usar_ia=False, salvar=False)

    assert not (carteira / "last_analysis.json").exists()
    assert list((carteira / "history").glob("*.json")) == []


def test_historico_em_ordem_cronologica_com_limite(dados_temp):
    for dia, valor in [(1, 100), (3, 300), (2, 200)]:
        registro = {
            "snapshot": {
                "data": f"2026-09-0{dia}",
                "totais": {
                    "valor_investido": 1000,
                    "valor_atual": valor,
                    "resultado": 0,
                    "resultado_pct": 0,
                },
                "saude_carteira": "boa",
            }
        }
        (dados_temp / "history" / f"2026-09-0{dia}.json").write_text(
            json.dumps(registro), encoding="utf-8"
        )

    serie = runner.historico()
    assert [s["data"] for s in serie] == ["2026-09-01", "2026-09-02", "2026-09-03"]
    assert [s["valor_atual"] for s in serie] == [100, 200, 300]
    assert [s["data"] for s in runner.historico(limite=2)] == ["2026-09-02", "2026-09-03"]


def test_historico_ignora_registros_invalidos(dados_temp):
    (dados_temp / "history" / "a.json").write_text("não é json", encoding="utf-8")
    (dados_temp / "history" / "b.json").write_text(json.dumps({"outro": 1}), encoding="utf-8")

    assert runner.historico() == []


def test_ultima_analise_sem_arquivo_ou_corrompido(dados_temp):
    assert runner.ultima_analise() is None
    (dados_temp / "last_analysis.json").write_text("{{{", encoding="utf-8")
    assert runner.ultima_analise() is None


# ─────────────────────────────────────────────
# CLI em processo
# ─────────────────────────────────────────────


def importar_cli():
    """Importa o script como módulo, sem executá-lo."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("analisar_cli", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_parser_reconhece_as_flags():
    parser = importar_cli().montar_parser()
    args = parser.parse_args(["--sem-ia", "--telegram", "--json"])

    assert args.sem_ia is True
    assert args.telegram is True
    assert args.json is True
    assert args.sem_cache is False


def test_enviar_ultima_exige_analise_anterior(dados_temp):
    cli = importar_cli()
    out, err = io.StringIO(), io.StringIO()

    codigo = cli.main(["--enviar-ultima", "--json"], out=out, err=err)

    assert codigo == 1
    assert json.loads(out.getvalue())["erro"].startswith("Rode uma análise antes")
    assert "[ERRO]" in err.getvalue()


# ─────────────────────────────────────────────
# CLI como processo (contrato com o servidor Node)
# ─────────────────────────────────────────────


def rodar_cli(args, dados_dir, extra_env=None):
    """Executa o script isolado num subprocesso, com a rede substituída."""
    mocks = dados_dir / "sitecustomize.py"
    mocks.write_text(
        "\n".join(
            [
                "import json",
                "class _R:",
                "    def __init__(self, corpo): self._c = corpo",
                "    def raise_for_status(self): pass",
                "    def json(self): return self._c",
                "def _get(url, params=None, headers=None, timeout=None):",
                "    if 'bcdata.sgs.433' in url: return _R([{'valor': '0,40'}])",
                "    if 'bcdata.sgs' in url: return _R([{'valor': '15,00'}])",
                "    if 'MXRF11.SA' in url:",
                "        return _R({'chart': {'result': [{'meta': {'regularMarketPrice': 12,"
                " 'chartPreviousClose': 11.9, 'longName': 'Maxi Renda'}}]}})",
                "    return _R({'chart': {'result': []}})",
                "import requests",
                "requests.get = _get",
            ]
        ),
        encoding="utf-8",
    )

    # .env próprio: modelo e esforço definidos, chave ausente. Sem isso o
    # subprocesso leria o .env real do projeto.
    env_ia = dados_dir / "ia.env"
    env_ia.write_text(
        "ANTHROPIC_ORIGEM_CHAVE=arquivo\n"
        "ANTHROPIC_MODEL=claude-opus-5\n"
        "ANTHROPIC_EFFORT=medium\n",
        encoding="utf-8",
    )

    ambiente = {
        **dict(__import__("os").environ),
        "PORTFOLIO_DATA_DIR": str(dados_dir),
        "PYTHONPATH": str(dados_dir),
        "IA_ENV_FILE": str(env_ia),
        "ANTHROPIC_API_KEY": "",
        "PYTHONIOENCODING": "utf-8",
        **(extra_env or {}),
    }

    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(RAIZ),
        env=ambiente,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def test_cli_sem_ia_imprime_relatorio_e_grava_historico(carteira):
    proc = rodar_cli(["--sem-ia"], carteira)

    assert proc.returncode == 0
    assert "RELATÓRIO DE CARTEIRA" in proc.stdout
    assert "R$ 12.000,00" in proc.stdout
    assert "Análise por IA desativada" in proc.stdout
    assert (carteira / "last_analysis.json").exists()
    assert len(list((carteira / "history").glob("*.json"))) == 1


def test_cli_json_separa_stdout_e_stderr(carteira):
    proc = rodar_cli(["--sem-ia", "--json"], carteira)

    assert proc.returncode == 0
    dados = json.loads(proc.stdout.strip())
    assert dados["snapshot"]["totais"]["valor_atual"] == 12000
    assert dados["ia"] is None

    assert "RELATÓRIO" not in proc.stdout, "o stdout carrega apenas o JSON"
    assert "[1/3]" in proc.stderr, "o progresso vai para o stderr"


def test_cli_relata_ia_indisponivel_sem_derrubar_o_relatorio(carteira):
    proc = rodar_cli([], carteira)

    assert proc.returncode == 0
    assert "Análise por IA indisponível: ANTHROPIC_API_KEY" in proc.stdout
    assert "RELATÓRIO DE CARTEIRA" in proc.stdout


def test_cli_nao_salvar(carteira):
    rodar_cli(["--sem-ia", "--json", "--nao-salvar"], carteira)

    assert not (carteira / "last_analysis.json").exists()
    assert list((carteira / "history").glob("*.json")) == []
