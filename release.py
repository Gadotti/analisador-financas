"""Empacota o release em `_deploys/<versao>.zip`.

A versão sai de `version.js` — a mesma exibida no rodapé da interface. Ficam de fora o
que o `.gitignore` já exclui (dados do usuário, `.env`, `node_modules`) e o material de
desenvolvimento listado em `CAMINHOS_IGNORADOS`.
"""

import re
import zipfile
from fnmatch import fnmatch
from pathlib import Path

# Material de desenvolvimento: existe no repositório, mas não vai para a máquina de quem usa.
CAMINHOS_IGNORADOS = {
    '.git',
    '.gitattributes',
    '.github',
    '.gitignore',
    '.claude',
    '.pytest_cache',
    '_deploys',
    'CLAUDE.md',
    'jest.config.mjs',
    'pytest.ini',
    'release.py',
    'test',
    'tests_analise',
}

# Arquivos renomeados com o sufixo -SAMPLE no zip, para que a instalação em produção
# não seja sobrescrita no deploy.
ARQUIVOS_EXEMPLO = set()


def ler_padroes_gitignore(caminho_gitignore):
    """Devolve os padrões do .gitignore, sem comentários, vazios e negações."""
    if not caminho_gitignore.exists():
        return []
    padroes = []
    for linha in caminho_gitignore.read_text(encoding='utf-8').splitlines():
        linha = linha.strip()
        if not linha or linha.startswith('#') or linha.startswith('!'):
            continue
        padroes.append(linha)
    return padroes


def _sufixos(caminho_relativo):
    """Caminho e cada sufixo dele: um padrão sem barra casa em qualquer nível."""
    partes = caminho_relativo.split('/')
    return ['/'.join(partes[i:]) for i in range(len(partes))]


def _casa_padrao(caminho_relativo, padrao_bruto):
    """Aplica um padrão do .gitignore, respeitando ancoragem e diretórios."""
    padrao = padrao_bruto.strip('/')
    ancorado = padrao_bruto.startswith('/') or '/' in padrao
    alvos = [caminho_relativo] if ancorado else _sufixos(caminho_relativo)
    return any(
        alvo == padrao or alvo.startswith(padrao + '/') or fnmatch(alvo, padrao)
        for alvo in alvos
    )


def esta_ignorado(caminho, padroes, base_dir):
    """Diz se o arquivo fica de fora do zip."""
    caminho_relativo = caminho.relative_to(base_dir).as_posix()
    if any(_casa_padrao(caminho_relativo, ignorado) for ignorado in CAMINHOS_IGNORADOS):
        return True
    return any(_casa_padrao(caminho_relativo, padrao) for padrao in padroes)


def ler_versao(caminho_versao):
    """Extrai a versão de `version.js` (`export const VERSAO = "1.2.3"`)."""
    conteudo = caminho_versao.read_text(encoding='utf-8')
    achado = re.search(r'VERSAO\s*=\s*["\']([^"\']+)["\']', conteudo)
    if not achado:
        raise ValueError(
            f'Versão não encontrada em {caminho_versao}: esperado '
            f'`export const VERSAO = "x.y.z"`, lido {conteudo.strip()!r}'
        )
    return achado.group(1)


def nome_no_zip(caminho_relativo):
    """Nome de destino dentro do zip, com o sufixo -SAMPLE quando for arquivo de exemplo."""
    if caminho_relativo.name not in ARQUIVOS_EXEMPLO:
        return caminho_relativo
    return caminho_relativo.with_name(
        f'{caminho_relativo.stem}-SAMPLE{caminho_relativo.suffix}'
    )


def criar_zip_release(base_dir):
    """Grava `_deploys/<versao>.zip` com os arquivos distribuíveis e devolve o caminho."""
    base_dir = Path(base_dir).resolve()
    versao = ler_versao(base_dir / 'version.js')
    pasta_deploy = base_dir / '_deploys'
    pasta_deploy.mkdir(exist_ok=True)
    caminho_zip = pasta_deploy / f'{versao}.zip'

    padroes = ler_padroes_gitignore(base_dir / '.gitignore')
    with zipfile.ZipFile(caminho_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for caminho in base_dir.rglob('*'):
            if caminho.is_dir() or caminho == caminho_zip:
                continue
            if esta_ignorado(caminho, padroes, base_dir):
                continue
            zipf.write(caminho, nome_no_zip(caminho.relative_to(base_dir)))
    return caminho_zip


if __name__ == '__main__':
    destino = criar_zip_release(Path(__file__).parent)
    print(f'Release criado com sucesso: {destino}')
