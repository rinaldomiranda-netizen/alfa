from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import subprocess, textwrap, os, sys
base=Path(r"C:\Users\Rinaldo CYBERSEGURYT\Desktop\ALFA\modules\sobrouplus")
out=base/"video_explicativo"
frames=out/"quadros"
frames.mkdir(parents=True,exist_ok=True)
W,H=1280,720
green="#0A563A"; vivid="#1FA361"; orange="#F57A20"; coral="#E74A3B"; cream="#FFF9EF"; dark="#12372A"; white="#FFFFFF"; muted="#527064"
fontdir=Path(r"C:\Windows\Fonts")
def font(size,bold=False):
    f=fontdir/("arialbd.ttf" if bold else "arial.ttf")
    return ImageFont.truetype(str(f),size)
scenes=[
("SOBROU+", "Boa comida. Mais valor. Menos desperdício.", "Uma plataforma para aproveitar alimentos próprios para consumo e reduzir perdas.", "INTRODUÇÃO"),
("O DESPERDÍCIO TEM CUSTO", "Alimentos bons podem sobrar no fim do dia.", "O comércio recupera parte do valor. O consumidor encontra oportunidades.", "POR QUE EXISTIMOS"),
("O COMÉRCIO SE CADASTRA", "O parceiro informa seus dados e unidades.", "Após o cadastro e a aprovação, organiza os produtos excedentes e suas condições.", "ETAPA 1"),
("A OFERTA É PUBLICADA", "Produto, quantidade, preço e horário.", "A loja define o que está disponível, o desconto e a janela de retirada ou entrega.", "ETAPA 2"),
("O CLIENTE ENCONTRA", "Veja ofertas disponíveis e escolha.", "O consumidor consulta os detalhes, compara valores e seleciona a opção desejada.", "ETAPA 3"),
("O PEDIDO É REALIZADO", "O sistema valida disponibilidade.", "A quantidade é conferida e o pedido segue para processamento conforme o meio habilitado.", "ETAPA 4"),
("A LOJA PREPARA", "O parceiro acompanha o pedido.", "A equipe recebe a solicitação, prepara os itens e atualiza o andamento.", "ETAPA 5"),
("RETIRADA OU ENTREGA", "Receba conforme a opção disponível.", "Na retirada, o pedido é conferido com código. No delivery, acompanha-se a etapa de entrega.", "ETAPA 6"),
("GESTÃO E IMPACTO", "Acompanhe vendas, estoque e resultados.", "O Sobrou+ reúne informações de pedidos, economia e alimentos recuperados, conforme os registros confirmados.", "GESTÃO"),
("MAIS VALOR. MENOS DESPERDÍCIO.", "Comércio, consumidores e comunidade.", "Conheça o Sobrou+ e ajude a dar destino melhor aos excedentes alimentares.", "SOBROU+")
]
def wrap(draw,txt,f,maxw):
    words=txt.split(); lines=[]; cur=""
    for w in words:
        test=(cur+" "+w).strip()
        if draw.textbbox((0,0),test,font=f)[2]<=maxw: cur=test
        else:
            if cur: lines.append(cur)
            cur=w
    if cur: lines.append(cur)
    return lines
for i,(title,sub,body,tag) in enumerate(scenes):
    im=Image.new("RGB",(W,H),cream); d=ImageDraw.Draw(im)
    d.rectangle((0,0,24,H),fill=green); d.rectangle((24,0,W,12),fill=orange)
    d.rounded_rectangle((70,60,310,105),radius=18,fill=green)
    d.text((88,69),tag,font=font(20,True),fill=white)
    d.text((70,150),title,font=font(58,True),fill=green)
    y=245
    for line in wrap(d,sub,font(36,True),1080):
        d.text((74,y),line,font=font(36,True),fill=dark); y+=48
    y+=22
    for line in wrap(d,body,font(28),1000):
        d.text((76,y),line,font=font(28),fill=muted); y+=42
    # illustrative interface card, clearly conceptual, not a real screenshot
    d.rounded_rectangle((830,390,1190,640),radius=28,fill=white,outline="#D9E8DE",width=3)
    if i in (2,3,4,5,6,7):
        d.rounded_rectangle((860,415,1160,462),radius=14,fill=green)
        d.text((880,426),"Sobrou+",font=font(25,True),fill=white)
        d.rounded_rectangle((860,480,1160,570),radius=16,fill="#EFF7F0")
        d.ellipse((880,497,938,555),fill="#D1E9D8")
        d.text((952,493),["Cadastro","Oferta do dia","Marmita","Pedido #1001","Preparando","Pronto para retirar"][i-2],font=font(20,True),fill=dark)
        d.text((952,524),"Exemplo ilustrativo",font=font(16),fill=muted)
        d.rounded_rectangle((860,586,1160,620),radius=12,fill=orange)
        d.text((920,592),"Acompanhar",font=font(18,True),fill=white)
    else:
        d.ellipse((900,435,1120,655),fill="#E8F4EA")
        d.ellipse((945,480,1075,610),fill=green)
        d.text((977,514),"S+",font=font(56,True),fill=white)
    d.text((74,670),"SOBROU+  •  DEMONSTRAÇÃO EXPLICATIVA",font=font(17,True),fill=muted)
    d.text((1170,665),f"{i+1:02d}/10",font=font(20,True),fill=green)
    im.save(frames/f"scene_{i+1:02d}.png")
# Build silent 150-second H.264 video from ten 15-second slides.
ff=Path(r"C:\Program Files\Kdenlive\bin\ffmpeg.exe")
concat=out/"quadros.txt"
concat.write_text("".join(f"file '{(frames/f'scene_{i+1:02d}.png').as_posix()}'\nduration 15\n" for i in range(10))+f"file '{(frames/'scene_10.png').as_posix()}'\n",encoding="utf-8")
silent=out/"SobrouPlus_video_sem_narracao.mp4"
cmd=[str(ff),"-y","-f","concat","-safe","0","-i",str(concat),"-vf","scale=1280:720,format=yuv420p","-r","25","-c:v","libx264","-preset","medium","-crf","22","-movflags","+faststart",str(silent)]
p=subprocess.run(cmd,capture_output=True,text=True)
print("FFMPEG_EXIT",p.returncode)
if p.returncode: print(p.stderr[-4000:]); sys.exit(p.returncode)
print("SILENT_VIDEO",silent,"SIZE",silent.stat().st_size)
