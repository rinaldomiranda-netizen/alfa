package com.beta.mobile

import android.content.Context
import org.json.JSONObject
import java.text.Normalizer

/**
 * Catálogo de TESTE local (ver assets/catalogo_teste.json) — ambiente
 * de demonstração da capacidade de a BETA consultar um sistema
 * comercial já existente (ver integrations/base.py no núcleo
 * desktop). NUNCA é um estoque real: não processa venda nem
 * pagamento, é só para provar a capacidade de integração/consulta.
 */
data class Produto(
    val nome: String,
    val preco: Double,
    val categoria: String,
    val marca: String = "",
    val estoque: Int = 0,
    val descricao: String = "",
)

/** Resposta da BETA a uma pergunta — o texto (falado/mostrado) e,
 * quando fizer sentido, os produtos em destaque (para exibir como
 * "cards" no Modo Aplicativo, ver Telas.kt). */
data class RespostaBeta(val texto: String, val produtos: List<Produto> = emptyList())

/**
 * Estados de um pagamento (item do pedido: "preparar arquitetura para
 * terminal de pagamento externo"). NENHUM terminal real está
 * conectado nesta entrega — isto é só a arquitetura pronta para
 * quando existir uma integração de verdade (PDV/TEF/POS/Pix). Usar
 * isto para fingir sucesso seria exatamente o que o pedido proíbe
 * ("não fingir sucesso"), então hoje só `AGUARDANDO_PAGAMENTO` é
 * alcançável — o resto existe apenas como contrato para o futuro.
 */
enum class EstadoPagamento { AGUARDANDO_PAGAMENTO, PAGAMENTO_EM_PROCESSAMENTO, PAGAMENTO_APROVADO, PAGAMENTO_RECUSADO, PAGAMENTO_CANCELADO }

/**
 * Controle de acesso DEFAULT DENY (item do pedido) — a BETA só pode
 * falar sobre o que está explicitamente permitido (produtos, estoque,
 * vendas, preço, formas de pagamento). Qualquer pedido que pareça
 * mirar dados financeiros/administrativos internos é recusado, sem
 * exceção e sem precisar de uma integração real pra isso ser
 * verdade — é uma barreira de conversa, testável hoje.
 */
object EscopoPermissoes {
    private val PALAVRAS_BLOQUEADAS = linkedMapOf(
        "financeiro" to "financeiro",
        "faturamento" to "financeiro",
        "bancari" to "dados bancários",
        "banco" to "dados bancários",
        "contabil" to "contabilidade",
        "folha de pagamento" to "folha de pagamento",
        "salario" to "folha de pagamento",
        "recursos humanos" to "recursos humanos",
        "credencial" to "credenciais",
        "senha do sistema" to "credenciais",
        "senha administrativa" to "credenciais",
        "segredo" to "segredos internos",
        "margem de lucro" to "margem/custo interno",
        "custo do produto" to "margem/custo interno",
    )

    /** Retorna uma recusa educada se a frase pedir algo fora do
     * escopo permitido, ou null se pode seguir normalmente. */
    fun verificarBloqueio(textoNormalizado: String): String? =
        PALAVRAS_BLOQUEADAS.entries.firstOrNull { textoNormalizado.contains(it.key) }
            ?.let { "Não tenho permissão para acessar informações de ${it.value}. Posso ajudar com produtos, preços e vendas do catálogo." }
}

/**
 * Entende PERGUNTAS/PEDIDOS completos (não só uma palavra) sobre o
 * catálogo de teste, com CONTEXTO de conversa (produto em foco,
 * quantidade, e um fluxo simples de confirmação de compra + pergunta
 * de forma de pagamento). É reconhecimento por PALAVRA-CHAVE + regras
 * + contexto — não é NLU com embeddings (não existe esse modelo
 * embarcado neste projeto).
 *
 * IMPORTANTE sobre pagamento: não existe NENHUM terminal/API de
 * pagamento real conectado. Quando a pessoa diz uma forma de
 * pagamento, a resposta é sempre a real ("não há sistema de
 * pagamento configurado neste Totem") — nunca finge sucesso (ver
 * "regra de verdade" do pedido).
 *
 * O contexto vive só em memória, por instância do app — nunca é
 * salvo em disco nem enviado a lugar nenhum.
 */
/** Um item da seleção/carrinho DEMO (item do pedido: "Quero três
 * produtos"/"Pode retirar a dipirona?" — precisa de mais de um item
 * simultâneo, não só um "produto em foco"). Vive só em memória. */
data class ItemCarrinho(val produto: Produto, var quantidade: Int)

class Catalogo(context: Context) {
    val produtos: List<Produto>

    private var ultimaBusca: List<Produto> = emptyList()
    private var produtoEmFoco: Produto? = null
    private var quantidadeEmFoco: Int = 1
    private var aguardandoConfirmacaoCompra = false
    private var aguardandoFormaPagamento = false
    private val carrinho = mutableListOf<ItemCarrinho>()
    private var aguardandoConfirmacaoRemocao: Produto? = null

    init {
        val texto = context.assets.open("catalogo_teste.json").bufferedReader().use { it.readText() }
        val json = JSONObject(texto)
        val lista = json.getJSONArray("produtos")
        val temp = mutableListOf<Produto>()
        for (i in 0 until lista.length()) {
            val item = lista.getJSONObject(i)
            temp.add(
                Produto(
                    nome = item.getString("nome"),
                    preco = item.getDouble("preco"),
                    categoria = item.getString("categoria"),
                    marca = item.optString("marca", ""),
                    estoque = item.optInt("estoque", 0),
                    descricao = item.optString("descricao", ""),
                ),
            )
        }
        produtos = temp
    }

    private fun normalizar(texto: String): String =
        Normalizer.normalize(texto.lowercase(), Normalizer.Form.NFD)
            .replace(Regex("\\p{Mn}+"), "")
            .trim()

    private fun preco(valor: Double) = "%.2f".format(valor).replace('.', ',')

    fun buscar(fraseCompleta: String): List<Produto> {
        val texto = normalizar(fraseCompleta)
        if (texto.isBlank()) return emptyList()
        return produtos.filter { produto ->
            val nome = normalizar(produto.nome)
            val categoria = normalizar(produto.categoria)
            val palavraChaveDoNome = nome.split(" ").firstOrNull { it.length >= 4 } ?: nome
            texto.contains(palavraChaveDoNome) || texto.contains(categoria) || nome.contains(texto)
        }
    }

    fun maisBaratos(quantidade: Int = 3): List<Produto> =
        produtos.sortedBy { it.preco }.take(quantidade)

    private val ordinais = mapOf(
        "primeira" to 1, "primeiro" to 1,
        "segunda" to 2, "segundo" to 2,
        "terceira" to 3, "terceiro" to 3,
        "quarta" to 4, "quarto" to 4,
    )

    private val numerosPorExtenso = mapOf(
        "uma" to 1, "um" to 1, "duas" to 2, "dois" to 2, "tres" to 3, "quatro" to 4,
        "cinco" to 5, "seis" to 6, "sete" to 7, "oito" to 8, "nove" to 9, "dez" to 10,
    )

    private fun ehSaudacao(t: String) =
        t == "ola" || t == "oi" || t.startsWith("ola ") || t.startsWith("oi ") ||
            t.startsWith("bom dia") || t.startsWith("boa tarde") || t.startsWith("boa noite")

    private fun ehAgradecimento(t: String) = t.contains("obrigad") || t.contains("valeu")
    private fun ehPedidoMaisBarato(t: String) = t.contains("mais barat")
    private fun ehPedidoOutro(t: String) = (t.contains(" outra") || t.contains(" outro") || t.startsWith("outra") || t.startsWith("outro")) && !t.contains("quanto")
    private fun extrairOrdinal(t: String): Int? = ordinais.entries.firstOrNull { t.contains(it.key) }?.value
    private fun ehPerguntaDePreco(t: String) = t.contains("quanto custa") || t.contains("qual o preco") || t.contains("qual preco") || t.contains("quanto e") || t.contains("quanto eh")
    private fun ehReferenciaVaga(t: String) =
        (t.contains("aquela") || t.contains("aquele") || t.contains(" essa") || t.contains(" esse") || t == "essa" || t == "esse") &&
            !ehPerguntaDePreco(t)

    private fun extrairQuantidade(t: String): Int? {
        Regex("(\\d+)\\s*(unidade|und)?").find(t)?.groupValues?.get(1)?.toIntOrNull()?.let { if (it in 1..999) return it }
        return numerosPorExtenso.entries.firstOrNull { t.contains(it.key) }?.value
    }

    private fun ehPerguntaTotal(t: String) = t.contains("quanto fica") || t.contains("quanto da tudo") || t.contains("quanto e no total") || t.contains("total")
    private fun ehIntencaoDeComprar(t: String) =
        t.contains("quero comprar") || t.contains("fechar pedido") || t.contains("fechar a compra") ||
            t.contains("quero fechar") || t.contains("quero finalizar") || t.contains("quero pagar") ||
            t.contains("confirmar compra") || t.contains("pode fechar")
    private fun ehAfirmativo(t: String) = t == "sim" || t.startsWith("sim") || t.contains("confirmo") || t.contains("pode confirmar") || t.contains("isso mesmo") || t.contains("confirmado")
    private fun ehNegativo(t: String) = t == "nao" || t.startsWith("nao") || t.contains("cancela") || t.contains("desisto")
    private fun ehMencaoFormaPagamento(t: String) = t.contains("pix") || t.contains("credito") || t.contains("debito") || t.contains("qr code") || t.contains("dinheiro") || t.contains("boleto")
    private fun ehPedidoRemover(t: String) =
        !t.contains("duvida") && !t.contains("foto") &&
            (t.contains("retirar") || t.contains("remover") || t.contains("tirar a") || t.contains("tirar o") ||
                t.contains("tire a") || t.contains("tire o") || t.contains("tira a") || t.contains("tira o"))
    private fun extrairFormaPagamento(t: String): String? = when {
        t.contains("pix") -> "PIX"
        t.contains("credito") -> "cartão de crédito"
        t.contains("debito") -> "cartão de débito"
        t.contains("dinheiro") -> "dinheiro"
        t.contains("boleto") -> "boleto"
        t.contains("qr code") -> "QR Code"
        else -> null
    }

    private fun upsertCarrinho(produto: Produto, quantidade: Int) {
        val existente = carrinho.find { it.produto == produto }
        if (existente != null) existente.quantidade = quantidade else carrinho.add(ItemCarrinho(produto, quantidade))
    }

    private fun totalCarrinho(): Double = carrinho.sumOf { it.produto.preco * it.quantidade }

    private fun resumoCarrinho(): String = carrinho.joinToString("; ") { "${it.quantidade}x ${it.produto.nome}" }

    /**
     * Ponto de entrada conversacional — recebe a frase COMPLETA (não
     * uma palavra), mantém contexto entre turnos, e nunca responde só
     * "produto encontrado": sempre com o nome/preço reais. Nunca
     * finge um pagamento ou venda real.
     */
    fun responderPergunta(pergunta: String, emModoDemo: Boolean = true): RespostaBeta {
        val texto = normalizar(pergunta)
        EscopoPermissoes.verificarBloqueio(texto)?.let { return RespostaBeta(it) }

        return when {
            ehSaudacao(texto) -> RespostaBeta("Olá! Em que posso ajudar você hoje?")
            ehAgradecimento(texto) -> RespostaBeta("Por nada! Posso ajudar em mais alguma coisa?")

            // Retirar item da seleção (item do pedido) — sempre confirma
            // antes de tirar, nunca remove direto.
            aguardandoConfirmacaoRemocao != null && ehAfirmativo(texto) -> confirmarRemocao()
            aguardandoConfirmacaoRemocao != null && ehNegativo(texto) -> cancelarRemocao()
            ehPedidoRemover(texto) -> responderPedirRemocao(pergunta)

            // Fluxo de venda/pagamento — ver docstring: em modo DEMO,
            // simula um pagamento SEMPRE identificado como "PAGAMENTO
            // DEMO"; fora do modo DEMO (aparelho licenciado de verdade,
            // sem terminal real conectado), nunca finge sucesso.
            aguardandoFormaPagamento && ehMencaoFormaPagamento(texto) -> responderPagamento(emModoDemo, texto)
            aguardandoConfirmacaoCompra && ehAfirmativo(texto) -> responderPedirFormaPagamento()
            aguardandoConfirmacaoCompra && ehNegativo(texto) -> responderCancelarCompra()
            ehIntencaoDeComprar(texto) && carrinho.isNotEmpty() -> responderConfirmarCompra()

            extrairOrdinal(texto) != null -> responderOrdinal(extrairOrdinal(texto)!!)
            ehPedidoMaisBarato(texto) -> responderMaisBarato()
            ehPedidoOutro(texto) -> responderOutro()
            ehPerguntaTotal(texto) -> responderTotal()
            // Só interpreta como "quantidade do produto em foco" quando a
            // frase não está claramente pedindo OUTRO produto (item do
            // pedido: "Quero uma dipirona" seguido de "quero uma
            // vitamina C" tem que trocar de produto, nunca reaproveitar
            // a quantidade num item errado).
            extrairQuantidade(texto) != null && produtoEmFoco != null &&
                buscar(pergunta).let { it.isEmpty() || produtoEmFoco in it } ->
                responderQuantidade(extrairQuantidade(texto)!!)
            ehPerguntaDePreco(texto) && buscar(pergunta).isEmpty() -> responderPrecoDoFoco()
            ehReferenciaVaga(texto) && produtoEmFoco == null && ultimaBusca.size > 1 -> pedirEsclarecimento()
            ehReferenciaVaga(texto) && produtoEmFoco != null -> responderPrecoDoFoco()
            else -> responderBuscaNova(pergunta)
        }
    }

    private fun pedirEsclarecimento(): RespostaBeta {
        val opcoes = ultimaBusca.mapIndexed { i, p -> "${ordinalPorExtenso(i + 1)} (${p.nome})" }.joinToString(", ")
        return RespostaBeta("Encontrei ${ultimaBusca.size} opções. Você quer a $opcoes?", ultimaBusca)
    }

    private fun ordinalPorExtenso(posicao: Int): String = when (posicao) {
        1 -> "primeira"; 2 -> "segunda"; 3 -> "terceira"; 4 -> "quarta"; else -> "${posicao}ª"
    }

    private fun responderBuscaNova(pergunta: String): RespostaBeta {
        val encontrados = buscar(pergunta)
        ultimaBusca = encontrados
        produtoEmFoco = encontrados.singleOrNull()
        quantidadeEmFoco = 1
        return when {
            encontrados.isEmpty() -> RespostaBeta("Não encontrei nada com esse nome no catálogo de teste. Pode descrever de outro jeito, ou dizer para que serve?")
            encontrados.size == 1 -> {
                val p = encontrados[0]
                upsertCarrinho(p, 1)
                val avisoEstoque = if (p.estoque <= 0) " Aviso: consta sem estoque no catálogo de teste agora." else ""
                RespostaBeta("${p.nome} custa R$ ${preco(p.preco)}, categoria ${p.categoria}, disponível.$avisoEstoque É essa que você procura?", encontrados)
            }
            else -> pedirEsclarecimento()
        }
    }

    private fun responderMaisBarato(): RespostaBeta {
        val base = ultimaBusca.ifEmpty { produtos }
        val item = base.minByOrNull { it.preco } ?: return RespostaBeta("Não encontrei opções para comparar.")
        produtoEmFoco = item
        quantidadeEmFoco = 1
        upsertCarrinho(item, 1)
        return RespostaBeta("A mais barata é ${item.nome}, por R$ ${preco(item.preco)}.", listOf(item))
    }

    private fun responderOutro(): RespostaBeta {
        if (ultimaBusca.size <= 1) return RespostaBeta("Não tenho outra opção parecida no catálogo de teste.")
        val indiceAtual = ultimaBusca.indexOf(produtoEmFoco)
        val proximo = ultimaBusca[(indiceAtual + 1).mod(ultimaBusca.size)]
        produtoEmFoco = proximo
        quantidadeEmFoco = 1
        upsertCarrinho(proximo, 1)
        return RespostaBeta("Também temos ${proximo.nome}, por R$ ${preco(proximo.preco)}.", listOf(proximo))
    }

    private fun responderOrdinal(posicao: Int): RespostaBeta {
        val item = ultimaBusca.getOrNull(posicao - 1)
            ?: return RespostaBeta("Não encontrei essa opção na lista que mostrei — pode repetir quais você quer comparar?")
        produtoEmFoco = item
        quantidadeEmFoco = 1
        upsertCarrinho(item, 1)
        return RespostaBeta("${item.nome} custa R$ ${preco(item.preco)}, categoria ${item.categoria}.", listOf(item))
    }

    private fun responderPrecoDoFoco(): RespostaBeta {
        val item = produtoEmFoco ?: return RespostaBeta("Sobre qual produto você quer saber o preço?")
        return RespostaBeta("${item.nome} custa R$ ${preco(item.preco)}.", listOf(item))
    }

    private fun responderQuantidade(quantidade: Int): RespostaBeta {
        val item = produtoEmFoco!!
        quantidadeEmFoco = quantidade
        upsertCarrinho(item, quantidade)
        val subtotal = item.preco * quantidade
        val avisoEstoque = if (item.estoque in 1 until quantidade) " Atenção: só há ${item.estoque} em estoque no catálogo de teste." else ""
        return RespostaBeta("Ok, $quantidade unidades de ${item.nome}. Fica R$ ${preco(subtotal)}.$avisoEstoque", listOf(item))
    }

    private fun responderTotal(): RespostaBeta {
        if (carrinho.isEmpty()) return RespostaBeta("Ainda não há nada selecionado para somar.")
        return RespostaBeta("${resumoCarrinho()}. Total: R$ ${preco(totalCarrinho())}.", carrinho.map { it.produto })
    }

    /** Retirar um item da seleção (item do pedido: "Pode retirar a
     * dipirona?") — nunca remove direto, sempre confirma primeiro com
     * o nome real do produto. */
    private fun responderPedirRemocao(pergunta: String): RespostaBeta {
        if (carrinho.isEmpty()) return RespostaBeta("Não há nada selecionado para retirar.")
        val encontrados = buscar(pergunta)
        val alvo = encontrados.firstOrNull { produto -> carrinho.any { it.produto == produto } }
            ?: carrinho.singleOrNull()?.produto
        if (alvo == null) return RespostaBeta("Qual item da seleção você quer retirar? Você tem: ${resumoCarrinho()}.")
        aguardandoConfirmacaoRemocao = alvo
        return RespostaBeta("Entendi que deseja retirar ${alvo.nome} da seleção. É isso mesmo?")
    }

    private fun confirmarRemocao(): RespostaBeta {
        val alvo = aguardandoConfirmacaoRemocao!!
        carrinho.removeAll { it.produto == alvo }
        if (produtoEmFoco == alvo) produtoEmFoco = null
        aguardandoConfirmacaoRemocao = null
        return RespostaBeta("Pronto, retirei ${alvo.nome} da seleção.")
    }

    private fun cancelarRemocao(): RespostaBeta {
        aguardandoConfirmacaoRemocao = null
        return RespostaBeta("Tudo bem, mantive na seleção.")
    }

    /** Antes de "concluir" qualquer coisa, sempre mostra o resumo do
     * carrinho INTEIRO e pergunta (item do pedido: "Você deseja
     * confirmar esta compra?") — nunca prossegue sem confirmação
     * explícita. */
    private fun responderConfirmarCompra(): RespostaBeta {
        aguardandoConfirmacaoCompra = true
        return RespostaBeta(
            "Resumo do pedido: ${resumoCarrinho()}. Total R$ ${preco(totalCarrinho())}. Você deseja confirmar esta compra?",
            carrinho.map { it.produto },
        )
    }

    private fun responderPedirFormaPagamento(): RespostaBeta {
        aguardandoConfirmacaoCompra = false
        aguardandoFormaPagamento = true
        return RespostaBeta("Como deseja pagar?")
    }

    private fun responderCancelarCompra(): RespostaBeta {
        aguardandoConfirmacaoCompra = false
        return RespostaBeta("Tudo bem, cancelei o pedido. Posso ajudar em mais alguma coisa?")
    }

    /** Item do pedido: "Não fingir integração real. Mostrar PAGAMENTO
     * DEMO quando for simulação." — em modo DEMO (sem licença real
     * ativada), simula um pagamento aprovado, SEMPRE identificado como
     * "PAGAMENTO DEMO", e limpa a seleção como uma venda concluiria de
     * verdade. Fora do modo DEMO, continua a "regra de verdade" — sem
     * terminal real conectado, nunca finge sucesso. */
    private fun responderPagamento(emModoDemo: Boolean, texto: String): RespostaBeta {
        aguardandoFormaPagamento = false
        if (!emModoDemo) {
            return RespostaBeta("Não há sistema de pagamento configurado neste Totem.")
        }
        if (carrinho.isEmpty()) return RespostaBeta("Não há um pedido em aberto para pagar.")
        val forma = extrairFormaPagamento(texto) ?: "forma selecionada"
        val total = totalCarrinho()
        val resposta = "PAGAMENTO DEMO — simulação de pagamento via $forma aprovada. Total R$ ${preco(total)}. Nenhuma cobrança real foi feita."
        carrinho.clear()
        produtoEmFoco = null
        return RespostaBeta(resposta)
    }
}
