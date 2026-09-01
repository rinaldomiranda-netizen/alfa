"""
Ferramenta do BETA_OWNER para emitir uma licença local assinada
(ver pedido "Sistema Central de Licenciamento").

NUNCA roda dentro do app (BETA Mobile/Desktop/Portátil) — a chave
privada (beta_owner_private_key.pem) fica só aqui, na máquina do
proprietário. O app instalado só carrega a chave PÚBLICA
(beta_owner_public_key.pem), embutida em
mobile/BetaMobile/app/src/main/kotlin/com/beta/mobile/licensing/LicenseVerifier.kt,
e usa ela só para VERIFICAR uma licença — nunca para assinar.

Formato do arquivo .beta-license gerado (2 linhas, UTF-8):
  linha 1: corpo da licença em JSON, uma linha só (é isto que é assinado)
  linha 2: assinatura RSA-SHA256 do corpo, em base64

Uso (módulos direto na linha de comando):
  python emitir_licenca.py --device-id <uuid> --modulos TOTEM,APLICATIVO
      --customer-id <id> [--dias-validade 365] [--edicao standard]
      [--max-dispositivos 1] --saida caminho/para/arquivo.beta-license

Uso (aprovação por checklist — item do pedido "sem código manual de
ativação": o proprietário marca módulos com números, nunca digita
nome de módulo nem qualquer código de ativação):
  python emitir_licenca.py --device-id <uuid> --customer-id <id>
      --interativo --saida caminho/para/arquivo.beta-license

Uso (a partir de um pedido gerado pelo próprio aparelho — cole o JSON
que o painel do proprietário no app mostrou/copiou):
  python emitir_licenca.py --solicitacao pedido.json --customer-id <id>
      --interativo --saida caminho/para/arquivo.beta-license
"""
import argparse
import base64
import datetime
import json
import subprocess
import sys
import uuid
from pathlib import Path

PASTA_SCRIPT = Path(__file__).resolve().parent
CHAVE_PRIVADA = PASTA_SCRIPT / "beta_owner_private_key.pem"

# Nunca remover um módulo já existente aqui — licenças antigas já
# assinadas referenciam esses nomes; removê-los mudaria silenciosamente
# a autorização de uma licença emitida antes desta atualização.
MODULOS_VALIDOS = {
    "TOTEM", "APLICATIVO", "ASSISTENTE", "DESKTOP", "INTEGRACAO_EMPRESA",
    "CATALOGO", "AUTOMACAO", "ACESSIBILIDADE", "CAMERA",
    "RECONHECIMENTO_FACIAL", "BETA_CLOUD", "MARKETPLACE", "ATUALIZACAO",
    "VOZ", "CAMERA_PRESENCA", "CAMERA_CONTAGEM", "PONTO_FUNCIONARIO", "PAGAMENTO",
    "CORE", "MOBILE", "PORTATIL", "CASA", "FAMILIA", "KIDS", "JOVEM",
    "CUIDADOS", "PET", "SEGURANCA", "EMERGENCIA", "TRABALHO", "APRESENTACAO",
    "ATENDIMENTO", "VENDAS", "ESTOQUE", "AVATAR_AVANCADO", "SKILLS",
}

# Espelha exatamente com.beta.mobile.licensing.Pacote — "pacote = conjunto
# de módulos" (item do pedido), nunca um mecanismo de autorização à parte.
PACOTES = {
    "BETA_START": {"ASSISTENTE", "APLICATIVO", "ACESSIBILIDADE"},
    "BETA_PROFESSIONAL": {"ASSISTENTE", "APLICATIVO", "ACESSIBILIDADE", "CATALOGO", "ATENDIMENTO", "VENDAS"},
    "BETA_TOTEM": {"TOTEM", "CATALOGO", "ATENDIMENTO", "VENDAS", "ESTOQUE", "ACESSIBILIDADE"},
    "BETA_BUSINESS": {"APLICATIVO", "TOTEM", "CATALOGO", "ATENDIMENTO", "VENDAS", "ESTOQUE", "INTEGRACAO_EMPRESA", "PONTO_FUNCIONARIO", "PAGAMENTO"},
    "BETA_FAMILY": {"ASSISTENTE", "CASA", "FAMILIA", "KIDS", "JOVEM", "CUIDADOS", "PET", "ACESSIBILIDADE"},
    "BETA_SECURITY": {"SEGURANCA", "EMERGENCIA", "CAMERA_PRESENCA", "CAMERA_CONTAGEM"},
    "BETA_ENTERPRISE": MODULOS_VALIDOS - {"KIDS", "JOVEM", "PET"},
    "BETA_CUSTOM": set(),
}


def escolher_modulos_interativo(pre_marcados=None):
    """Checklist numerado (item do pedido: "proprietário marca os
    módulos... sem código manual") — nunca pede pra digitar nome de
    módulo, só números, e ENTER vazio confirma a seleção atual."""
    pre_marcados = set(pre_marcados or [])
    lista = sorted(MODULOS_VALIDOS)
    marcados = set(pre_marcados)
    while True:
        print("\nMódulos (toque o número para marcar/desmarcar, ENTER vazio confirma):")
        for i, nome in enumerate(lista, start=1):
            marca = "[x]" if nome in marcados else "[ ]"
            print(f"  {i:2d}. {marca} {nome}")
        entrada = input("Número (ou ENTER para confirmar): ").strip()
        if entrada == "":
            if not marcados:
                print("Selecione ao menos um módulo antes de confirmar.")
                continue
            return sorted(marcados)
        if not entrada.isdigit() or not (1 <= int(entrada) <= len(lista)):
            print("Número inválido.")
            continue
        escolhido = lista[int(entrada) - 1]
        if escolhido in marcados:
            marcados.remove(escolhido)
        else:
            marcados.add(escolhido)


def assinar(corpo_bytes: bytes) -> str:
    """Assina com openssl (chave privada nunca sai desta função pro
    resto do processo além do argumento de arquivo temporário)."""
    if not CHAVE_PRIVADA.exists():
        raise SystemExit(f"Chave privada não encontrada em {CHAVE_PRIVADA} — gere com openssl antes.")
    processo = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(CHAVE_PRIVADA)],
        input=corpo_bytes,
        capture_output=True,
        check=True,
    )
    return base64.b64encode(processo.stdout).decode("ascii")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--device-id", help="device_id do aparelho autorizado (UUID) — obrigatório sem --solicitacao")
    parser.add_argument("--solicitacao", help="arquivo JSON do pedido de ativação gerado pelo painel do proprietário no app (preenche device_id e módulos solicitados)")
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--organization-id", default="")
    parser.add_argument("--modulos", help="lista separada por vírgula, ex.: TOTEM,APLICATIVO (dispensável com --interativo/--pacote)")
    parser.add_argument("--pacote", choices=sorted(PACOTES), help="usa o conjunto de módulos de um pacote comercial pronto (item do pedido: 'Pacote = conjunto de módulos')")
    parser.add_argument("--interativo", action="store_true", help="mostra checklist numerado de módulos em vez de exigir --modulos (item do pedido: sem código manual)")
    parser.add_argument("--bonus", help="módulos temporários, ex.: KIDS:30,KIDS_MUSICA:60 (dias) — item do pedido 'BONUS_MODULE'")
    parser.add_argument("--edicao", default="standard")
    parser.add_argument("--max-dispositivos", type=int, default=1)
    parser.add_argument("--dias-validade", type=int, default=365, help="0 = sem expiração (não recomendado)")
    parser.add_argument("--saida", required=True)
    args = parser.parse_args()

    modulos_solicitados = []
    device_id = args.device_id
    if args.solicitacao:
        pedido = json.loads(Path(args.solicitacao).read_text(encoding="utf-8"))
        device_id = device_id or pedido.get("device_id")
        modulos_solicitados = pedido.get("requested_modules", [])
        print(f"Pedido carregado: device_id={pedido.get('device_id')} plataforma={pedido.get('platform')} status={pedido.get('status')}")

    if not device_id:
        raise SystemExit("Informe --device-id ou --solicitacao com um device_id.")

    if args.pacote:
        modulos = sorted(PACOTES[args.pacote])
    elif args.interativo:
        modulos = escolher_modulos_interativo(pre_marcados=modulos_solicitados)
    elif args.modulos:
        modulos = [m.strip().upper() for m in args.modulos.split(",") if m.strip()]
    else:
        raise SystemExit("Informe --modulos, --pacote ou --interativo.")

    invalidos = [m for m in modulos if m not in MODULOS_VALIDOS]
    if invalidos:
        raise SystemExit(f"Módulo(s) desconhecido(s): {invalidos}. Válidos: {sorted(MODULOS_VALIDOS)}")

    bonus_modules = {}
    if args.bonus:
        agora_bonus = datetime.datetime.now(datetime.timezone.utc)
        for par in args.bonus.split(","):
            par = par.strip()
            if not par:
                continue
            nome, _, dias_texto = par.partition(":")
            nome = nome.strip().upper()
            if nome not in MODULOS_VALIDOS:
                raise SystemExit(f"Módulo de bônus desconhecido: {nome}. Válidos: {sorted(MODULOS_VALIDOS)}")
            try:
                dias = int(dias_texto)
            except ValueError:
                raise SystemExit(f"Prazo de bônus inválido para {nome}: {dias_texto!r} (use MODULO:DIAS, ex. KIDS:30)")
            bonus_modules[nome] = (agora_bonus + datetime.timedelta(days=dias)).isoformat()

    agora = datetime.datetime.now(datetime.timezone.utc)
    expira = None if args.dias_validade == 0 else agora + datetime.timedelta(days=args.dias_validade)

    corpo = {
        "license_id": str(uuid.uuid4()),
        "customer_id": args.customer_id,
        "organization_id": args.organization_id,
        "device_id": device_id,
        "status": "active",
        "issued_at": agora.isoformat(),
        "expires_at": expira.isoformat() if expira else None,
        "modules": sorted(modulos),
        "edition": args.edicao,
        "max_devices": args.max_dispositivos,
        "bonus_modules": bonus_modules,
    }

    linha_corpo = json.dumps(corpo, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    assinatura = assinar(linha_corpo.encode("utf-8"))

    caminho_saida = Path(args.saida)
    caminho_saida.write_text(linha_corpo + "\n" + assinatura + "\n", encoding="utf-8")
    print(f"Licença emitida: {caminho_saida}")
    print(f"device_id: {device_id}")
    print(f"módulos: {corpo['modules']}")
    if bonus_modules:
        print(f"módulos bônus: {bonus_modules}")
    print(f"expira em: {corpo['expires_at']}")


if __name__ == "__main__":
    main()
