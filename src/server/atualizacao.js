/**
 * Verifica se há uma versão mais nova publicada no GitHub.
 *
 * A imagem Docker e a release do Git saem do mesmo workflow, na mesma tag
 * (`.github/workflows/release.yml`), então uma consulta única cobre tanto
 * quem roda no host quanto quem roda em container — não há necessidade de
 * consultar o GHCR separadamente.
 *
 * Falha de rede nunca deve impedir o uso do sistema (mesmo princípio de
 * `market.cotacao`, no lado Python): devolve `disponivel: false` com o erro,
 * nunca lança.
 */

import { VERSAO } from "../../version.js";

const REPOSITORIO = "Gadotti/analisador-financas";
const URL_ULTIMA_RELEASE = `https://api.github.com/repos/${REPOSITORIO}/releases/latest`;

// Suficiente para não bater na API do GitHub a cada carregamento da tela —
// o limite sem autenticação é 60 chamadas/hora por IP.
const VALIDADE_CACHE_MS = 6 * 60 * 60 * 1000;

let cache = null;

/** Compara "x.y.z" — o único formato de versão que este projeto usa. */
function ehMaisNova(remota, local) {
  const partes = (v) => v.split(".").map((n) => Number.parseInt(n, 10) || 0);
  const a = partes(remota);
  const b = partes(local);
  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    if ((a[i] || 0) !== (b[i] || 0)) return (a[i] || 0) > (b[i] || 0);
  }
  return false;
}

async function buscarResultado(buscar) {
  try {
    const resposta = await buscar(URL_ULTIMA_RELEASE, {
      headers: { Accept: "application/vnd.github+json" },
    });
    if (!resposta.ok) {
      throw new Error(`GitHub respondeu ${resposta.status} ao consultar a última release.`);
    }
    const release = await resposta.json();
    const versaoDisponivel = String(release.tag_name || "").replace(/^v/, "");
    return {
      versao_atual: VERSAO,
      versao_disponivel: versaoDisponivel || null,
      disponivel: Boolean(versaoDisponivel) && ehMaisNova(versaoDisponivel, VERSAO),
      url: release.html_url || null,
      publicado_em: release.published_at || null,
      erro: null,
    };
  } catch (erro) {
    return {
      versao_atual: VERSAO,
      versao_disponivel: null,
      disponivel: false,
      url: null,
      publicado_em: null,
      erro: erro.message,
    };
  }
}

/**
 * Consulta a última release do GitHub e compara com `VERSAO`.
 *
 * `buscar` substitui o `fetch` global nos testes; `agora` e `forcar` isolam
 * o cache em memória, que existe só para poupar chamadas repetidas à API.
 */
export async function consultarAtualizacao({ buscar = fetch, agora = Date.now(), forcar = false } = {}) {
  if (!forcar && cache && cache.expiraEm > agora) return cache.resultado;

  const resultado = await buscarResultado(buscar);
  cache = { expiraEm: agora + VALIDADE_CACHE_MS, resultado };
  return resultado;
}

/** Descarta o cache — usado só entre testes. */
export function reiniciar() {
  cache = null;
}
