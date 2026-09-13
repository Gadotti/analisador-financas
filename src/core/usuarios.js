/**
 * Cadastro de usuários do login e segredo de sessão — data/usuarios.json.
 *
 * Login não é configuração do .env: é dado do cadastro, como a carteira, e
 * aceita mais de um usuário — todos autenticam contra os mesmos dados, sem
 * segregação nenhuma (o login só existe para liberar o acesso à ferramenta).
 *
 * Fica em data/, não em .env, de propósito: o volume de dados do Docker é
 * gravável dentro do container, o que .env (montado :ro no docker-compose.yml)
 * não é — dá para criar ou trocar a senha de um usuário rodando
 * `docker compose exec ... node scripts/criarLogin.js` sem tocar no compose.
 */

import crypto from "node:crypto";
import fs from "node:fs";

import { garantirDiretorios, usuariosFile } from "../config/paths.js";
import { conferirSenha, gerarHashSenha } from "./authService.js";

/** Nenhum usuário cadastrado ainda, ou arquivo corrompido. */
export class AutenticacaoError extends Error {
  constructor(mensagem) {
    super(mensagem);
    this.name = "AutenticacaoError";
  }
}

const vazio = () => ({ segredo_sessao: "", usuarios: [] });

/** Lê data/usuarios.json; devolve a lista vazia se o arquivo ainda não existir. */
function carregar() {
  let bruto;
  try {
    bruto = fs.readFileSync(usuariosFile(), "utf8");
  } catch {
    return vazio();
  }

  let dados;
  try {
    dados = JSON.parse(bruto);
  } catch (erro) {
    throw new AutenticacaoError(`${usuariosFile()} não é um JSON válido: ${erro.message}`);
  }
  return {
    segredo_sessao: typeof dados.segredo_sessao === "string" ? dados.segredo_sessao : "",
    usuarios: Array.isArray(dados.usuarios) ? dados.usuarios : [],
  };
}

function salvar(dados) {
  garantirDiretorios();
  const destino = usuariosFile();
  const temporario = `${destino}.tmp`;
  fs.writeFileSync(temporario, JSON.stringify(dados, null, 2), "utf8");
  fs.renameSync(temporario, destino);
}

/**
 * Usuários e segredo de sessão cadastrados.
 * Lança AutenticacaoError quando ainda não existe nenhum usuário — é o
 * estado antes do primeiro `node scripts/criarLogin.js`.
 */
export function configuracaoAuth() {
  const dados = carregar();
  if (!dados.usuarios.length || !dados.segredo_sessao) {
    throw new AutenticacaoError(
      `Nenhum usuário cadastrado em ${usuariosFile()}. Rode "node scripts/criarLogin.js" para criar o login.`,
    );
  }
  return dados;
}

/** Usuário autenticado (o próprio nome) em caso de sucesso, ou null. */
export function conferirCredenciais(usuarios, usuario, senha) {
  if (typeof usuario !== "string" || typeof senha !== "string") return null;
  const encontrado = usuarios.find((u) => u.usuario === usuario);
  if (!encontrado) return null;
  return conferirSenha(senha, encontrado.senha_hash) ? encontrado.usuario : null;
}

/**
 * Cria um usuário novo ou troca a senha de um já cadastrado.
 * Gera o segredo de sessão na primeira vez e preserva o já existente —
 * trocar o segredo derrubaria a sessão de todo mundo, não só a de quem está
 * mudando a própria senha.
 */
export function criarOuAtualizarUsuario(usuario, senha) {
  const dados = carregar();
  if (!dados.segredo_sessao) dados.segredo_sessao = crypto.randomBytes(32).toString("hex");

  const senhaHash = gerarHashSenha(senha);
  const existente = dados.usuarios.find((u) => u.usuario === usuario);
  const criado = !existente;
  if (existente) existente.senha_hash = senhaHash;
  else dados.usuarios.push({ usuario, senha_hash: senhaHash });

  salvar(dados);
  return { criado };
}
