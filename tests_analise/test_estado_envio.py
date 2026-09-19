"""Deduplicação do envio ao Telegram: hash estável, anotação, poda e registro."""

from analise import estado_envio


def alerta(titulo="Concentracao em MXRF11: 54.5%", descricao="A posicao representa 54.5%."):
    return {"titulo": titulo, "descricao": descricao}


def fato(ativo="MXRF11", titulo="Distribuição mantida", descricao="Provento estável."):
    return {"ativo": ativo, "titulo": titulo, "descricao": descricao}


# ─────────────────────────────────────────────
# Hash: estável, e muda com o texto
# ─────────────────────────────────────────────

def test_hash_do_mesmo_texto_e_igual():
    assert estado_envio.hash_alerta(alerta()) == estado_envio.hash_alerta(alerta())


def test_hash_muda_quando_o_texto_muda():
    original = estado_envio.hash_alerta(alerta())
    mudou = estado_envio.hash_alerta(alerta(titulo="Concentracao em MXRF11: 60.0%"))

    assert original != mudou


def test_hash_de_fato_leva_o_ativo_em_conta():
    """Dois fatos com o mesmo título, em ativos diferentes, não podem colidir."""
    assert estado_envio.hash_fato(fato(ativo="MXRF11")) != estado_envio.hash_fato(fato(ativo="HGLG11"))


# ─────────────────────────────────────────────
# marcar: anotação para a tela
# ─────────────────────────────────────────────

def test_marcar_anota_enviado_telegram_conforme_o_estado():
    enviado = alerta()
    novo = alerta(titulo="Outro alerta")
    estado = {"alertas": [estado_envio.hash_alerta(enviado)]}

    anotados = estado_envio.marcar([enviado, novo], "alertas", estado)

    assert anotados[0]["enviado_telegram"] is True
    assert anotados[1]["enviado_telegram"] is False


def test_marcar_nao_muta_o_item_original():
    original = alerta()
    estado_envio.marcar([original], "alertas", {"alertas": [estado_envio.hash_alerta(original)]})

    assert "enviado_telegram" not in original


# ─────────────────────────────────────────────
# podar: sem histórico, só o que ainda existe hoje
# ─────────────────────────────────────────────

def test_podar_mantem_so_hashes_de_achados_ainda_presentes():
    presente = alerta()
    estado = {
        "alertas": [estado_envio.hash_alerta(presente), "hash-de-algo-que-sumiu"],
        "riscos_ia": [],
        "fatos_ia": [],
    }

    podado = estado_envio.podar(estado, {"alertas": [presente], "riscos_ia": [], "fatos_ia": []})

    assert podado["alertas"] == [estado_envio.hash_alerta(presente)]


def test_podar_descarta_tudo_quando_a_leitura_de_hoje_esta_vazia():
    estado = {"alertas": [estado_envio.hash_alerta(alerta())], "riscos_ia": [], "fatos_ia": []}

    podado = estado_envio.podar(estado, {"alertas": [], "riscos_ia": [], "fatos_ia": []})

    assert podado["alertas"] == []


# ─────────────────────────────────────────────
# registrar_envio: acrescenta sem duplicar
# ─────────────────────────────────────────────

def test_registrar_envio_acrescenta_as_chaves_novas():
    estado = {"alertas": ["h1"], "riscos_ia": [], "fatos_ia": []}

    novo = estado_envio.registrar_envio(estado, {"alertas": ["h1", "h2"], "fatos_ia": ["h3"]})

    assert novo["alertas"] == ["h1", "h2"]
    assert novo["fatos_ia"] == ["h3"]
    assert novo["riscos_ia"] == []


# ─────────────────────────────────────────────
# ler/gravar: o ciclo completo em disco
# ─────────────────────────────────────────────

def test_ler_sem_arquivo_devolve_vazio(dados_temp):
    assert estado_envio.ler() == {}


def test_gravar_e_ler_fazem_o_ciclo(dados_temp):
    estado_envio.gravar({"alertas": ["h1"], "riscos_ia": [], "fatos_ia": []})

    assert estado_envio.ler() == {"alertas": ["h1"], "riscos_ia": [], "fatos_ia": []}


def test_ler_arquivo_corrompido_devolve_vazio(dados_temp):
    (dados_temp / "telegram_enviados.json").write_text("{ nao é json", encoding="utf-8")

    assert estado_envio.ler() == {}
