package com.beta.mobile.ui

import androidx.camera.core.CameraSelector
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView

/**
 * Câmera FRONTAL sob demanda (ver pedido do mobile: "captura sob
 * comando", "não gravar vídeo contínuo") — só mostra a prévia ao
 * vivo enquanto esta tela estiver visível; nenhum frame é salvo em
 * disco por este composable. Reconhecimento facial NÃO está
 * implementado nesta primeira versão (ver relatório) — isto é só o
 * mecanismo de captura.
 */
@Composable
fun CameraPreview(modifier: Modifier = Modifier) {
    val contexto = LocalContext.current
    val ciclosDeVida = LocalLifecycleOwner.current

    AndroidView(
        modifier = modifier.fillMaxWidth().height(240.dp),
        factory = { ctx ->
            val previewView = PreviewView(ctx)
            val futureProvider = ProcessCameraProvider.getInstance(ctx)
            futureProvider.addListener({
                val provider = futureProvider.get()
                val preview = Preview.Builder().build().also {
                    it.surfaceProvider = previewView.surfaceProvider
                }
                try {
                    provider.unbindAll()
                    provider.bindToLifecycle(ciclosDeVida, CameraSelector.DEFAULT_FRONT_CAMERA, preview)
                } catch (_: Exception) {
                    // Sem câmera frontal disponível neste aparelho/emulador —
                    // best-effort, nunca derruba o app (ver pedido: câmera é
                    // opcional).
                }
            }, androidx.core.content.ContextCompat.getMainExecutor(ctx))
            previewView
        },
    )
}
