"use strict";
const $=s=>document.querySelector(s);
let sessionId=null;
$("#perfil").textContent="empresa da sua sessão";
const empresa=()=>"";

function add(text,kind='beta'){
 if(!text)return;
 const div=document.createElement('div');
 div.className='msg '+kind; div.textContent=text;
 $('#messages').appendChild(div); $('#messages').scrollTop=$('#messages').scrollHeight;
}
function setStatus(s){
 $('#status').textContent=s ? (s.estado+' · '+(s.nome_pessoa||'sem nome')+' · '+(s.atendimento_id||'sem ID')) : 'Nenhum atendimento ativo';
}
async function api(path,opts){
 const r=await fetch(path,{headers:{'Content-Type':'application/json','X-RMD':'1'},...opts});
 const d=await r.json(); if(r.status===401){location.href='/';} if(!r.ok)throw new Error(d.erro||'Erro'); return d;
}
async function novo(){
 sessionId=null; $('#messages').innerHTML=''; add('Iniciando novo atendimento...','system');
 const d=await api('/api/recepcao/atendimentos',{method:'POST',body:JSON.stringify({empresa_id:empresa()})});
 sessionId=d.session_id; add(d.mensagem); setStatus(d.status);
 if(d.proxima_pergunta && d.proxima_pergunta!==d.mensagem)add(d.proxima_pergunta,'beta');
 carregarHistorico();
}
async function enviar(e){
 e.preventDefault(); const texto=$('#texto').value.trim(); if(!texto)return;
 if(!sessionId)await novo();
 add(texto,'user'); $('#texto').value='';
 try{
  const d=await api('/api/recepcao/atendimentos/'+sessionId+'/mensagens',{method:'POST',body:JSON.stringify({empresa_id:empresa(),texto:texto})});
  if(d.mensagem)add(d.mensagem);
  if(d.proxima_pergunta && d.proxima_pergunta!==d.mensagem)add(d.proxima_pergunta,'beta');
  setStatus(d.status);
  if(d.status && d.status.ativo===false){
   add('Atendimento concluído e salvo no histórico.','system'); sessionId=null; carregarHistorico();
  }
 }catch(err){add(err.message,'system');}
}
async function finalizar(){
 if(!sessionId){add('Não há atendimento ativo.','system');return;}
 const d=await api('/api/recepcao/atendimentos/'+sessionId+'/finalizar',{method:'POST',body:JSON.stringify({empresa_id:empresa()})});
 add('Atendimento finalizado e salvo.','system'); setStatus(d.status); sessionId=null; carregarHistorico();
}
async function carregarHistorico(){
 try{
  const d=await api('/api/recepcao/historico',{method:'GET'});
  const box=$('#historico'); box.innerHTML='';
  if(!d.itens.length){box.innerHTML='<div class="empty">Nenhum registro.</div>';return;}
  d.itens.forEach(x=>{
   const b=document.createElement('button');
   b.textContent=(x.atendimento_id||'sem ID')+' · '+(x.nome_pessoa||'sem nome')+' · '+(x.estado||'');
   b.onclick=()=>add('Registro '+(x.atendimento_id||'')+'\nNome: '+(x.nome_pessoa||'-')+'\nEstado: '+(x.estado||'-')+'\nDados: '+JSON.stringify(x.respostas||{},null,2),'system');
   box.appendChild(b);
  });
 }catch(err){$('#historico').innerHTML='<div class="empty">Falha ao carregar histórico.</div>';}
}
async function health(){
 try{const d=await api('/api/health',{method:'GET'});$('#health').textContent='online · '+d.versao;}
 catch{$('#health').textContent='offline';}
}
$('#novo').onclick=()=>novo().catch(e=>add(e.message,'system'));
$('#finalizar').onclick=()=>finalizar().catch(e=>add(e.message,'system'));
$('#atualizar').onclick=carregarHistorico;
$('#form').onsubmit=enviar;
health(); carregarHistorico();
