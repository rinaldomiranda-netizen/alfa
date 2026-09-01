"""
Skills — extensões específicas de aplicativo em cima das ferramentas
genéricas do agente (ver agente/). Cada skill só existe quando o
aplicativo correspondente exige uma forma de controle mais confiável
do que "abrir + simular teclado + OCR" (ver agente/orquestrador.py
para o caminho genérico, ainda usado para qualquer app sem skill
própria).

Word/Excel/PowerPoint usam automação COM (win32com.client, já uma
dependência do projeto via pywin32) em vez de UI Automation/coordenadas
— é a interface que o próprio Office expõe para automação e é mais
robusta e rápida que simular cliques num grid de células, por exemplo.
100% local: nenhuma chamada de rede.

Não existe (e não precisa existir) skills/windows, arquivos, camera,
pesquisa ou atendimento — essas capacidades já são módulos maduros do
projeto (computer/, vision/camera.py, core/atendimento.py) e não
ganhariam nada sendo reembrulhadas aqui.
"""
