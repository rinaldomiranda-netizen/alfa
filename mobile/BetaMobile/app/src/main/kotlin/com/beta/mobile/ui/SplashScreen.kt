package com.beta.mobile.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.beta.mobile.R
import com.beta.mobile.avatar.AvatarState
import com.beta.mobile.avatar.BetaAvatar
import kotlinx.coroutines.delay

/**
 * Splash 100% offline (item 16 do pedido) — sequência fixa:
 * 1) logo BETA, 2) avatar, 3) "SISTEMA ALPHA", 4) RMD, 5) frase
 * institucional, 6) rodapé — e então navega sozinha para a seleção
 * de modo. Duração configurável via `duracaoMs` (ver
 * Preferencias.duracaoSplashMs), nunca fixa em três lugares
 * diferentes do código.
 */
@Composable
fun SplashScreen(duracaoMs: Long, aoTerminar: () -> Unit) {
    var etapa by remember { mutableIntStateOf(0) }

    LaunchedEffect(duracaoMs) {
        val passo = (duracaoMs / 6).coerceAtLeast(150L)
        repeat(5) {
            delay(passo)
            etapa += 1
        }
        val restante = duracaoMs - passo * 5
        if (restante > 0) delay(restante)
        aoTerminar()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(FundoBeta)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        AnimatedVisibility(visible = etapa >= 0, enter = fadeIn(tween(500))) {
            Text(
                "BETA",
                color = AzulNeon,
                fontSize = 56.sp,
                fontWeight = FontWeight.Bold,
            )
        }

        Spacer(Modifier.height(20.dp))

        AnimatedVisibility(visible = etapa >= 1, enter = fadeIn(tween(600))) {
            BetaAvatar(estado = AvatarState.IDLE, tamanho = 140)
        }

        Spacer(Modifier.height(20.dp))

        AnimatedVisibility(visible = etapa >= 2, enter = fadeIn(tween(500))) {
            Text(
                "SISTEMA ALPHA",
                color = MaterialTheme.colorScheme.onBackground,
                fontSize = 16.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }

        Spacer(Modifier.height(6.dp))

        AnimatedVisibility(visible = etapa >= 3, enter = fadeIn(tween(500))) {
            Text(
                "RMD",
                color = DouradoDiscreto,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium,
            )
        }

        Spacer(Modifier.height(24.dp))

        AnimatedVisibility(visible = etapa >= 4, enter = fadeIn(tween(600))) {
            Text(
                stringResource(R.string.frase_institucional),
                color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.8f),
                fontSize = 13.sp,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
        }

        Spacer(Modifier.weight(1f))

        AnimatedVisibility(visible = etapa >= 5, enter = fadeIn(tween(500))) {
            Text(
                stringResource(R.string.rodape_copyright),
                color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.5f),
                fontSize = 11.sp,
                textAlign = TextAlign.Center,
            )
        }
    }
}
