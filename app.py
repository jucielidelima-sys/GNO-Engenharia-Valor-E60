import io
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Persistência: Supabase em produção; SQLite apenas para testes locais.
import json
import sqlite3
import hmac
import requests
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parent / 'storage' / 'e60_simulacoes.sqlite3'
PERSIST_KEYS = ['simulacoes_itens_e60', 'tempos_crono_e60_segundos_descricao_v2', 'projetos_ativos',
                'taxa_hora_integrado', 'aprovados_integrado', 'incluir_crono_integrado',
                'crono_integracao_selecoes_e60']

st.set_page_config(page_title='E60 | Engenharia de Valor', page_icon='🏭', layout='wide')

def secret(name):
    try:
        return str(st.secrets.get(name, '')).strip()
    except (FileNotFoundError, KeyError):
        return ''

SUPABASE_URL = secret('SUPABASE_URL').rstrip('/')
SUPABASE_KEY = secret('SUPABASE_KEY')
APP_PASSWORD = secret('APP_PASSWORD')
USE_CLOUD = bool(SUPABASE_URL and SUPABASE_KEY)

# Não expor dados industriais em uma implantação pública sem senha.
if not APP_PASSWORD and (USE_CLOUD or secret('REQUIRE_LOGIN') == 'true'):
    st.error('Configure APP_PASSWORD nos Secrets antes de usar o banco online.')
    st.stop()
if APP_PASSWORD and not st.session_state.get('_e60_authenticated', False):
    st.title('🔒 Acesso GNO — Engenharia de Valor E60')
    with st.form('login_e60'):
        candidate = st.text_input('Senha de acesso', type='password')
        submitted = st.form_submit_button('Entrar')
    if submitted:
        if hmac.compare_digest(candidate, APP_PASSWORD):
            st.session_state['_e60_authenticated'] = True
            st.rerun()
        else:
            st.error('Senha incorreta.')
    st.stop()

if bool(SUPABASE_URL) != bool(SUPABASE_KEY):
    st.error('Configuração incompleta: SUPABASE_URL e SUPABASE_KEY são obrigatórios em conjunto.')
    st.stop()

def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('CREATE TABLE IF NOT EXISTS snapshots (id INTEGER PRIMARY KEY, saved_at TEXT NOT NULL, payload TEXT NOT NULL)')
    return con

def encode_value(v):
    if isinstance(v, pd.DataFrame):
        return {'type': 'dataframe', 'data': v.to_json(orient='split', date_format='iso')}
    return {'type': 'json', 'data': v}

def decode_value(v):
    if v['type'] == 'dataframe':
        return pd.read_json(io.StringIO(v['data']), orient='split')
    return v['data']

def export_state():
    return {k: encode_value(st.session_state[k]) for k in PERSIST_KEYS if k in st.session_state}

def restore_state(payload):
    for k, v in payload.items():
        if k in PERSIST_KEYS:
            st.session_state[k] = decode_value(v)

def cloud_request(method, params=None, body=None):
    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=representation',
    }
    response = requests.request(
        method, SUPABASE_URL + '/rest/v1/e60_snapshots',
        headers=headers, params=params, json=body, timeout=25,
    )
    response.raise_for_status()
    return response.json()

def save_snapshot(payload):
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    if USE_CLOUD:
        # Inserção append-only: versões antigas não são sobrescritas.
        rows = cloud_request('POST', body={'payload': payload})
        return rows[0]['saved_at'] if rows else datetime.now(timezone.utc).isoformat()
    with connect_db() as con:
        timestamp = datetime.now(timezone.utc).isoformat()
        con.execute('INSERT INTO snapshots(saved_at,payload) VALUES (?,?)', (timestamp, data))
        con.execute('DELETE FROM snapshots WHERE id NOT IN (SELECT id FROM snapshots ORDER BY id DESC LIMIT 30)')
    return timestamp

def latest_snapshot():
    if USE_CLOUD:
        rows = cloud_request('GET', params={'select': 'id,saved_at,payload', 'order': 'id.desc', 'limit': '1'})
        if rows:
            return rows[0]['saved_at'], rows[0]['payload']
        return None
    with connect_db() as con:
        row = con.execute('SELECT saved_at,payload FROM snapshots ORDER BY id DESC LIMIT 1').fetchone()
        return (row[0], json.loads(row[1])) if row else None

if '_persist_loaded' not in st.session_state:
    try:
        snap = latest_snapshot()
        if snap:
            restore_state(snap[1])
        st.session_state['_persist_loaded'] = True
        st.session_state['_last_persisted'] = json.dumps(export_state(), ensure_ascii=False, allow_nan=False)
        st.session_state['_last_saved_at'] = snap[0] if snap else None
    except Exception as exc:
        st.error('Não foi possível carregar os dados salvos. Nenhuma edição será permitida até a conexão voltar.')
        st.code(str(exc))
        st.stop()

# Identidade visual GNO: painel industrial, alto contraste e indicadores operacionais.
st.markdown("""<style>
:root {--gno:#f15a24;--ink:#182331;}
.block-container {padding-top:1.4rem;max-width:1550px;}
h1,h2,h3 {letter-spacing:-.025em;}
h1 {font-size:2rem!important;color:#f15a24!important;font-weight:800!important;}
[data-testid="stMetric"] {background:#172433;border:1px solid #344453;border-left:5px solid #f15a24;border-radius:8px;padding:17px 18px;min-height:115px;}
[data-testid="stMetricLabel"] p {color:#d2dbe5!important;font-weight:650!important;text-transform:uppercase;letter-spacing:.06em;font-size:.78rem!important;}
[data-testid="stMetricValue"] {color:#fff!important;font-weight:800!important;}
[data-testid="stMetricDelta"] {font-weight:700!important;}
[data-testid="stTabs"] button[aria-selected="true"] {color:#f15a24!important;border-bottom-color:#f15a24!important;}
[data-testid="stSidebar"] {border-right:3px solid #f15a24;}
.gno-kicker {font-size:.78rem;font-weight:800;letter-spacing:.16em;color:#f15a24;text-transform:uppercase;}
.gno-strip {border-left:5px solid #f15a24;padding:10px 16px;background:#172433;color:white;border-radius:6px;margin:8px 0 18px;}
.gno-strip small {color:#cbd5e1;}
</style>""",unsafe_allow_html=True)
logo_path = Path(__file__).resolve().parent / 'assets' / 'logo_gno.png'
header_logo, header_text = st.columns([1, 5], vertical_alignment='center')
with header_logo:
    if logo_path.exists():
        st.image(str(logo_path), use_container_width=True)
with header_text:
    st.markdown('<div class="gno-kicker">GRUPO NEW ORDER · ENGENHARIA INDUSTRIAL</div>',unsafe_allow_html=True)
    st.title('ENGENHARIA DE VALOR | E60')
    st.caption('BOM multinível • Cronoanálise • Substituição de componentes • Viabilidade')

# Base E60 incorporada no código: não requer planilha externa ou upload.
# Conteúdo original XLSX compactado com zlib e codificado em base64.
import base64
import zlib
E60_XLSX_EMBUTIDO = (
    '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'
    '=='
)

@st.cache_data
def carregar():
    conteudo = zlib.decompress(base64.b64decode(E60_XLSX_EMBUTIDO))
    return pd.read_excel(io.BytesIO(conteudo), header=None, engine='openpyxl')

try:
    raw = carregar()
except Exception as exc:
    st.error(f'Não foi possível carregar os dados incorporados do E60: {exc}')
    st.stop()

def numero(v,default=0.0):
    try:return float(v) if pd.notna(v) else default
    except (TypeError,ValueError):return default

# A linha 10 do relatório (índice 9) é o resumo do produto, não um item da BOM.
produto=str(raw.iat[9,2]) if raw.shape[0]>9 else 'E60'
custo=numero(raw.iat[9,7]) if raw.shape[1]>7 else 0
custo_direto=numero(raw.iat[9,5]) if raw.shape[1]>5 else 0
cif=numero(raw.iat[9,6]) if raw.shape[1]>6 else 0
if not custo:st.warning('Custo padrão não identificado no cabeçalho da ficha. Confira o layout da planilha.')

# A ficha alterna linhas de materiais, processos e subtotais de conjuntos.
# Não somar a coluna de custos de todas as linhas: isso duplica níveis.
colunas=['Estágio','Centro de custo','Produto / código','Derivação','Descrição','Complemento','Consumo','Unidade','Custo direto unit.','CIF','Custo padrão','Entrada/Saída']
bom=raw.iloc[10:,:12].copy()
bom.columns=colunas
bom=bom.dropna(how='all').reset_index(drop=True)
# Correção validada da base de cronoanálise: OP-019, Montagem Fornos II - RDO.
# A origem da BOM usa minutos; 2.824,362 segundos = 47,0727 minutos.
_filtro_op019 = (bom['Descrição'].astype(str).str.strip() == 'Montagem Fornos II - RDO') & (bom['Unidade'].astype(str).str.strip().str.upper() == 'M')
if _filtro_op019.sum() != 1:
    st.error('Não foi possível identificar unicamente a operação OP-019 na base. Correção não aplicada.')
    st.stop()
bom.loc[_filtro_op019, 'Consumo'] = 2824.362 / 60.0
for c in ['Consumo','Custo direto unit.','CIF','Custo padrão']:
    bom[c]=pd.to_numeric(bom[c],errors='coerce')

projetos_iniciais=[
 ('Embalagem','Redesenho EPS e caixa',34.14,3.00,5.00,'Médio','Ensaios de queda, vibração e empilhamento'),
 ('Montagem','Balanceamento, dispositivos e fixadores',38.45,2.00,4.00,'Médio','Cronoanálise e teste de montagem'),
 ('Comprados','Chicote, fechos, vidros e comandos',53.62,1.90,4.90,'Alto','Homologação, segurança elétrica e térmica'),
 ('Chapas','Tampas da base',12.56,0.60,1.20,'Médio','Rigidez, vibração e tolerâncias'),
 ('Chapas','Laterais da cobertura',12.18,0.60,1.40,'Médio','Dilatação e estabilidade dimensional'),
 ('Chapas','Frontal e nesting',20.68,0.80,1.80,'Médio','Aparência, dimensional e acabamento'),
 ('Esmaltação','Aproveitamento de chapa e esmalte',25.53,0.75,1.50,'Alto','Ciclos térmicos e aderência do esmalte'),
]
proj=pd.DataFrame(projetos_iniciais,columns=['Área','Projeto','Base de referência (R$)','Mínimo (R$)','Máximo (R$)','Risco','Validação exigida'])

if logo_path.exists():
    st.sidebar.image(str(logo_path), use_container_width=True)
st.sidebar.markdown('### ⚙️ Parâmetros de produção')
volume=st.sidebar.number_input('Produção mensal (unidades)',min_value=0,value=3000,step=100)
investimento=st.sidebar.number_input('Investimento total previsto (R$)',min_value=0.0,value=25000.0,step=1000.0)
abas=st.tabs(['📊 Visão geral','🧩 Estrutura BOM','🛠️ Projetos de redução','📐 Chapas','💰 Viabilidade','⚠️ Riscos','⏱️ Cronoanálise','🔁 Simulação de itens','📈 Painel integrado'])
with abas[0]:
    st.subheader(produto)
    a,b,c,d=st.columns(4)
    a.metric('Custo padrão',f'R$ {custo:,.2f}')
    b.metric('Custo direto',f'R$ {custo_direto:,.2f}')
    c.metric('CIF',f'R$ {cif:,.2f}')
    d.metric('Projetos propostos',len(proj))
    st.markdown('<div class="gno-strip"><b>PAINEL DE CONTROLE DE CUSTOS</b><br><small>Indicadores de engenharia e potencial de melhoria · valores de referência, não ganhos realizados</small></div>',unsafe_allow_html=True)
    x,y,z=st.columns(3)
    x.metric('Custo direto / total',f'{100*custo_direto/custo:.1f}%' if custo else '—')
    y.metric('CIF / total',f'{100*cif/custo:.1f}%' if custo else '—')
    z.metric('Potencial bruto máximo',f'R$ {proj["Máximo (R$)"].sum():,.2f}')
    st.info('A ficha é multinível: subtotais e operações não devem ser somados novamente. Potenciais de projetos podem se sobrepor.')
    st.markdown('#### RADAR DE OPORTUNIDADES | ENGENHARIA DE VALOR')
    st.caption('Ranking por economia máxima estimada por forno. Faixa mínima–máxima é uma hipótese técnica, não resultado realizado.')
    radar = st.session_state.get('projetos_ativos', proj).copy()
    required = ['Área', 'Projeto', 'Mínimo (R$)', 'Máximo (R$)']
    if isinstance(radar, pd.DataFrame) and all(col in radar.columns for col in required):
        radar['Mínimo (R$)'] = pd.to_numeric(radar['Mínimo (R$)'], errors='coerce').fillna(0).clip(lower=0)
        radar['Máximo (R$)'] = pd.to_numeric(radar['Máximo (R$)'], errors='coerce').fillna(0).clip(lower=0)
        radar = radar[radar['Máximo (R$)'] >= radar['Mínimo (R$)']].sort_values('Máximo (R$)', ascending=True)
        fig = go.Figure()
        for _, item in radar.iterrows():
            fig.add_trace(go.Bar(
                x=[float(item['Máximo (R$)'])], y=[str(item['Projeto'])], orientation='h',
                marker=dict(color='#F15A24', line=dict(color='#E54D19', width=0.5)),
                text=[f"R$ {item['Máximo (R$)']:.2f}".replace('.', ',')],
                textposition='outside', cliponaxis=False, showlegend=False,
                customdata=[[str(item['Área']), float(item['Mínimo (R$)'])]],
                hovertemplate='<b>%{y}</b><br>Área: %{customdata[0]}<br>Mínimo: R$ %{customdata[1]:.2f}<br>Máximo: R$ %{x:.2f}<extra></extra>'
            ))
        fig.update_layout(
            template='plotly_white', paper_bgcolor='#FFFFFF', plot_bgcolor='#FFFFFF',
            font=dict(color='#253244', size=13), height=max(410, 66 * len(radar) + 100),
            margin=dict(l=16, r=90, t=28, b=45), bargap=0.30,
            xaxis=dict(title='Economia potencial máxima (R$/forno)', gridcolor='#E5E7EB', zeroline=False, tickprefix='R$ '),
            yaxis=dict(title='', automargin=True, tickfont=dict(color='#253244', size=12)),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption('Todas as oportunidades em laranja GNO; a área de cada projeto aparece ao passar o mouse sobre a barra.')
        st.caption('Painel de engenharia com dados da BOM e hipóteses cadastradas; não há telemetria em tempo real ou integração com máquinas.')
    else:
        st.warning('A carteira de projetos não contém todas as colunas necessárias para o radar.')

with abas[1]:
    st.subheader('Explorador da ficha original')
    busca=st.text_input('Filtrar por código, descrição ou complemento')
    vista=bom.copy()
    if busca:
        mask=vista.astype(str).apply(lambda s:s.str.contains(busca,case=False,regex=False)).any(axis=1)
        vista=vista[mask]
    st.dataframe(vista,use_container_width=True,hide_index=True,height=550)
    st.caption('Linhas reproduzidas conforme relatório de origem; os níveis e os subtotais permanecem visíveis para auditoria.')
with abas[2]:
    st.subheader('Carteira de oportunidades — hipóteses, não economias realizadas')
    editado=st.data_editor(st.session_state.get('projetos_ativos',proj),num_rows='dynamic',use_container_width=True,hide_index=True,key='projetos')
    st.session_state['projetos_ativos']=editado
    st.download_button('Exportar projetos CSV',editado.to_csv(index=False).encode('utf-8-sig'),'projetos_e60.csv','text/csv')
with abas[3]:
    st.subheader('Simulador de alteração de espessura e blank')
    x,y,z=st.columns(3)
    with x:
        largura=st.number_input('Largura do blank (mm)',min_value=1.0,value=500.0)
        comprimento=st.number_input('Comprimento do blank (mm)',min_value=1.0,value=600.0)
        qtd=st.number_input('Quantidade por forno',min_value=1,value=2)
    with y:
        e0=st.number_input('Espessura atual (mm)',min_value=0.1,value=0.40,step=0.01,format='%.2f')
        e1=st.number_input('Espessura proposta (mm)',min_value=0.1,value=0.35,step=0.01,format='%.2f')
        aproveitamento=st.slider('Aproveitamento da chapa (%)',1,100,85)
    with z:
        densidade=st.number_input('Densidade (kg/m³)',min_value=100.0,value=7850.0)
        preco=st.number_input('Preço da chapa (R$/kg)',min_value=0.0,value=7.0,step=0.5)
        custo_extra=st.number_input('Custo adicional de processo (R$/forno)',min_value=0.0,value=0.0,step=0.1)
    area=largura*comprimento/1e6
    m0=area*(e0/1000)*densidade*qtd
    m1=area*(e1/1000)*densidade*qtd
    economia=(m0-m1)*preco/(aproveitamento/100)-custo_extra
    a,b,c=st.columns(3)
    a.metric('Massa atual (kg/forno)',f'{m0:.3f}')
    b.metric('Massa proposta (kg/forno)',f'{m1:.3f}',delta=f'{m1-m0:.3f} kg')
    c.metric('Economia teórica (R$/forno)',f'{economia:.2f}')
    st.warning('Modelo geométrico simplificado: não considera dobras, recortes, nervuras, perdas reais por nesting, ferramental ou resistência mecânica. Não autoriza redução de espessura sem validação.')
with abas[4]:
    st.subheader('Simulação econômica consolidada')
    p=st.session_state.get('projetos_ativos',proj)
    minimo=pd.to_numeric(p['Mínimo (R$)'],errors='coerce').fillna(0).sum()
    maximo=pd.to_numeric(p['Máximo (R$)'],errors='coerce').fillna(0).sum()
    escolhido=st.slider('Economia por forno considerada (R$)',0.0,float(max(1,maximo)),float(min(maximo,(minimo+maximo)/2)),0.05)
    st.caption(f'Intervalo bruto das hipóteses: R$ {minimo:.2f} a R$ {maximo:.2f} por forno. Verificar sobreposições antes de consolidar.')
    mensal=volume*escolhido
    a,b,c,d=st.columns(4)
    a.metric('Novo custo simulado',f'R$ {custo-escolhido:,.2f}')
    b.metric('Redução',f'{100*escolhido/custo:.2f}%' if custo else '—')
    c.metric('Economia anual bruta',f'R$ {mensal*12:,.2f}')
    d.metric('Payback simples',f'{investimento/mensal:.1f} meses' if mensal else '—')
    st.caption('Não inclui custos recorrentes, tributos, inflação, depreciação, capacidade ociosa ou efeitos de implantação.')
with abas[5]:
    st.subheader('Checklist de homologação')
    for titulo,desc in [('Segurança elétrica','Isolação, aterramento, chicotes, conectores e temperaturas'),('Segurança térmica','Dilatação, deformação, isolamento e ciclos de operação'),('Estrutura metálica','Rigidez, tolerâncias, vibração e resistência dos fixadores'),('Esmaltação','Aderência, espessura de camada e choque térmico'),('Embalagem','Queda, vibração, empilhamento e avarias'),('Custos reais','Cotações, tempos medidos, refugo, ferramental e custo recorrente')]:
        st.checkbox(f'{titulo} — {desc}',key='risco_'+titulo)
    st.caption('Os checklists são locais à sessão; para uso colaborativo, a próxima versão deverá persistir os dados em banco ou repositório.')


# Módulo independente: comparação dos tempos de processo cadastrados x nova cronoanálise.
with abas[6]:
    st.subheader('⏱️ Tempos padrão × Nova cronoanálise')
    st.caption('Base de tempos incorporada ao app. Não é necessário enviar Excel.')
    st.warning('Tempos convertidos de minutos (M) para segundos (s), multiplicando por 60. Confirme no ERP que M significa minutos e verifique a base de quantidade antes de calcular economia.')
    linhas_tempo=[]
    contexto_codigo=''
    contexto_descricao=''
    for idx, r in bom.iterrows():
        unidade=str(r.get('Unidade','')).strip().upper()
        # Linhas de cabeçalho de subconjuntos: código do item na primeira coluna.
        est=str(r.get('Estágio','')).strip()
        centro=str(r.get('Centro de custo','')).strip()
        if est not in ('nan','None') and centro in ('1','1.0') and str(r.get('Produto / código','')).strip() not in ('nan','None'):
            contexto_codigo=est
            contexto_descricao=str(r.get('Produto / código',''))
        if unidade=='M' and pd.notna(r.get('Consumo')):
            linhas_tempo.append({
                'ID': f'OP-{idx+11:03d}',
                'Conjunto / código': contexto_codigo or 'E60 (nível principal)',
                'Estágio': est,
                'Descrição do item': contexto_descricao or 'NARDELLI EMBUTIR 60L BLACK',
                'Operação': str(r.get('Descrição','')).strip(),
                'Centro de custo': str(r.get('Centro de custo','')).strip(),
                'Tempo padrão (s)': float(r['Consumo']) * 60,
                'Novo tempo (s)': None,
                'Amostras (n)': None,
                'Observações': '',
            })
    tempos_base=pd.DataFrame(linhas_tempo)
    st.info(f'{len(tempos_base)} registros de operação identificados na ficha original (origem M, exibidos em segundos). Os tempos de diferentes níveis da BOM não devem ser somados como tempo total do forno sem verificar multiplicidades e roteiros.')
    # Migração por ID: mantém medições anteriores e acrescenta o estágio da ficha.
    chave_crono='tempos_crono_e60_segundos_descricao_v2'
    anterior=st.session_state.get(chave_crono)
    if not isinstance(anterior,pd.DataFrame) or 'ID' not in anterior.columns:
        st.session_state[chave_crono]=tempos_base.copy()
    else:
        base_atual=tempos_base.copy().set_index('ID',drop=False)
        anterior=anterior.drop_duplicates(subset=['ID'],keep='last').set_index('ID',drop=False)
        for coluna in ['Novo tempo (s)','Amostras (n)','Observações']:
            if coluna in anterior.columns:
                comuns=base_atual.index.intersection(anterior.index)
                base_atual.loc[comuns,coluna]=anterior.loc[comuns,coluna]
        st.session_state[chave_crono]=base_atual.reset_index(drop=True)
    pesquisa=st.text_input('Pesquisar descrição do item, operação, código ou centro de custo',key='busca_crono')
    # Migração conservadora: corrige somente o tempo padrão antigo da OP-019,
    # inclusive em snapshots já carregados do Supabase; mantém novas medições.
    _crono_atual = st.session_state['tempos_crono_e60_segundos_descricao_v2'].copy()
    _op019 = _crono_atual['ID'].astype(str).eq('OP-019')
    if _op019.sum() == 1:
        _valor_anterior = pd.to_numeric(_crono_atual.loc[_op019, 'Tempo padrão (s)'], errors='coerce').iloc[0]
        if pd.notna(_valor_anterior) and abs(float(_valor_anterior) - 1882.908) < 0.02:
            _crono_atual.loc[_op019, 'Tempo padrão (s)'] = 2824.362
            st.session_state['tempos_crono_e60_segundos_descricao_v2'] = _crono_atual
    editavel=st.session_state['tempos_crono_e60_segundos_descricao_v2'].copy()
    if pesquisa:
        filtro=editavel[['Conjunto / código','Estágio','Descrição do item','Operação','Centro de custo']].astype(str).apply(lambda col:col.str.contains(pesquisa,case=False,regex=False)).any(axis=1)
        visiveis=editavel.loc[filtro].copy()
    else:
        visiveis=editavel.copy()
    novo=st.data_editor(visiveis,hide_index=True,use_container_width=True,height=490,key='editor_crono_segundos_descricao_v2',disabled=['ID','Conjunto / código','Estágio','Descrição do item','Operação','Centro de custo','Tempo padrão (s)'],column_config={
        'Tempo padrão (s)':st.column_config.NumberColumn(format='%.2f'),
        'Novo tempo (s)':st.column_config.NumberColumn(format='%.2f',min_value=0),
        'Amostras (n)':st.column_config.NumberColumn(min_value=1,step=1),
    })
    editavel.loc[novo.index,['Novo tempo (s)','Amostras (n)','Observações']]=novo[['Novo tempo (s)','Amostras (n)','Observações']]
    st.session_state['tempos_crono_e60_segundos_descricao_v2']=editavel
    comp=editavel.copy()
    comp['Diferença (s)']=pd.to_numeric(comp['Novo tempo (s)'],errors='coerce')-comp['Tempo padrão (s)']
    comp['Variação (%)']=100*comp['Diferença (s)']/comp['Tempo padrão (s)'].replace(0,float('nan'))
    medidos=comp.dropna(subset=['Novo tempo (s)'])
    a,b,c=st.columns(3)
    a.metric('Operações cadastradas',len(comp))
    b.metric('Operações cronometradas',len(medidos))
    c.metric('Diferença média (%)',f"{medidos['Variação (%)'].mean():+.1f}%" if len(medidos) else '—')
    st.dataframe(comp.loc[comp['Novo tempo (s)'].notna(),['ID','Conjunto / código','Estágio','Descrição do item','Operação','Tempo padrão (s)','Novo tempo (s)','Diferença (s)','Variação (%)']],hide_index=True,use_container_width=True)
    st.download_button('⬇️ Exportar confronto de tempos (CSV)',comp.to_csv(index=False,sep=';',decimal=',').encode('utf-8-sig'),file_name='E60_confronto_cronoanalise.csv',mime='text/csv')
    st.caption('Os lançamentos permanecem na sessão do navegador. Exporte o CSV para guardar os resultados; a publicação no GitHub não armazena automaticamente os lançamentos de todos os usuários.')


with abas[7]:
    st.subheader('🔁 Substituição de itens e simulação de novos preços')
    st.caption('Compare cada componente da ficha com uma alternativa: caixa atual × nova caixa, fornecedor atual × novo fornecedor, material atual × material proposto.')
    st.warning('A estrutura é multinível: a mesma peça pode aparecer em diferentes níveis. A economia total abaixo é uma soma de cenários selecionados, NÃO uma redução validada do custo total do forno. Valide a quantidade efetiva por forno e elimine sobreposições antes de aprovar.')
    # Selecionar somente linhas de saída de componentes; excluir operações e cabeçalhos/subtotais.
    itens=bom.loc[bom['Entrada/Saída'].astype(str).str.strip().str.lower().eq('saída') & bom['Produto / código'].notna()].copy()
    itens['Consumo']=pd.to_numeric(itens['Consumo'],errors='coerce')
    itens['Custo padrão']=pd.to_numeric(itens['Custo padrão'],errors='coerce')
    itens=itens.loc[itens['Consumo'].gt(0) & itens['Custo padrão'].notna()].copy()
    itens['Código']=itens['Produto / código'].astype(str).str.strip()
    itens['Custo unitário (R$)']=itens['Custo padrão']/itens['Consumo']
    itens['Descrição original']=itens['Descrição'].fillna('').astype(str)
    itens['Unidade']=itens['Unidade'].fillna('').astype(str)
    itens['Referência']=itens.index.map(lambda x: f'LIN-{x+11:04d}')
    itens=itens[['Referência','Código','Descrição original','Unidade','Consumo','Custo unitário (R$)','Custo padrão']].rename(columns={'Consumo':'Qtd na linha','Custo padrão':'Custo atual na linha (R$)'})
    itens=itens.reset_index(drop=True)
    st.info(f'{len(itens)} linhas de materiais/componentes identificadas. Custos unitários calculados dividindo o custo total da linha pelo consumo cadastrado.')
    filtro_item=st.text_input('Pesquisar código ou descrição',key='filtro_substituicoes')
    vista_itens=itens.copy()
    if filtro_item:
        m=vista_itens[['Código','Descrição original']].astype(str).apply(lambda c:c.str.contains(filtro_item,case=False,regex=False)).any(axis=1)
        vista_itens=vista_itens[m]
    st.dataframe(vista_itens,hide_index=True,use_container_width=True,height=270,column_config={
        'Custo unitário (R$)':st.column_config.NumberColumn(format='R$ %.4f'),
        'Custo atual na linha (R$)':st.column_config.NumberColumn(format='R$ %.4f'),
    })
    st.markdown('#### Criar uma simulação')
    opcoes=itens['Referência'].tolist()
    if opcoes:
        escolhida=st.selectbox('Item original',opcoes,format_func=lambda x: (lambda r:f"{r['Código']} | {r['Descrição original'][:65]} | R$ {r['Custo unitário (R$)']:.4f}/{r['Unidade']}")(itens.loc[itens['Referência'].eq(x)].iloc[0]),key='item_simulacao')
        original=itens.loc[itens['Referência'].eq(escolhida)].iloc[0]
        a,b,c=st.columns(3)
        with a:
            novo_codigo=st.text_input('Código do novo item (opcional)',key='novo_codigo_item')
            nova_descricao=st.text_input('Descrição da alternativa',placeholder='Ex.: Nova caixa de papelão reforçada',key='nova_desc_item')
        with b:
            novo_preco=st.number_input(f'Novo custo unitário (R$/{original["Unidade"]})',min_value=0.0,value=float(original['Custo unitário (R$)']),step=0.1,format='%.4f',key=f'preco_{escolhida}')
            qtd_proposta=st.number_input('Quantidade proposta por forno / ocorrência',min_value=0.0,value=float(original['Qtd na linha']),step=1.0,format='%.4f',key=f'qtd_{escolhida}')
        with c:
            risco=st.selectbox('Risco técnico',['Baixo','Médio','Alto'],key='risco_simulacao')
            situacao=st.selectbox('Status',['Em estudo','Aguardando amostra','Em teste','Aprovado','Reprovado'],key='status_simulacao')
        observacao=st.text_input('Fornecedor, justificativa e testes necessários',key='obs_simulacao')
        custo_proposto=novo_preco*qtd_proposta
        economia=float(original['Custo atual na linha (R$)'])-custo_proposto
        m1,m2,m3=st.columns(3)
        m1.metric('Custo atual na linha',f"R$ {original['Custo atual na linha (R$)']:.2f}")
        m2.metric('Custo proposto',f'R$ {custo_proposto:.2f}')
        m3.metric('Economia por ocorrência',f'R$ {economia:+.2f}')
        if 'simulacoes_itens_e60' not in st.session_state:
            st.session_state['simulacoes_itens_e60']=[]
        if st.button('➕ Adicionar alternativa ao cenário',type='primary'):
            if not nova_descricao.strip():
                st.error('Informe a descrição do novo item.')
            else:
                st.session_state['simulacoes_itens_e60'].append({
                    'Referência':escolhida,'Código atual':original['Código'],'Descrição atual':original['Descrição original'],
                    'Código novo':novo_codigo,'Descrição nova':nova_descricao,'Unidade':original['Unidade'],
                    'Qtd atual':float(original['Qtd na linha']),'Custo unit. atual (R$)':float(original['Custo unitário (R$)']),
                    'Custo atual (R$)':float(original['Custo atual na linha (R$)']),
                    'Qtd nova':float(qtd_proposta),'Custo unit. novo (R$)':float(novo_preco),
                    'Risco':risco,'Status':situacao,'Observações':observacao,
                    'Considerar no cenário':True,
                })
                st.success('Alternativa adicionada ao cenário.')
    st.markdown('#### Cenário de substituições')
    sims=st.session_state.get('simulacoes_itens_e60',[])
    if sims:
        tabela=pd.DataFrame(sims)
        edit=st.data_editor(tabela,num_rows='dynamic',hide_index=True,use_container_width=True,key='editor_alternativas_e60',column_config={
            'Considerar no cenário':st.column_config.CheckboxColumn('Incluir?'),
            'Custo unit. novo (R$)':st.column_config.NumberColumn(min_value=0,format='R$ %.4f'),
            'Qtd nova':st.column_config.NumberColumn(min_value=0,format='%.4f'),
            'Status':st.column_config.SelectboxColumn(options=['Em estudo','Aguardando amostra','Em teste','Aprovado','Reprovado']),
            'Risco':st.column_config.SelectboxColumn(options=['Baixo','Médio','Alto']),
        },disabled=['Referência','Código atual','Descrição atual','Unidade','Qtd atual','Custo unit. atual (R$)','Custo atual (R$)'])
        edit['Custo unit. novo (R$)']=pd.to_numeric(edit['Custo unit. novo (R$)'],errors='coerce').fillna(0).clip(lower=0)
        edit['Qtd nova']=pd.to_numeric(edit['Qtd nova'],errors='coerce').fillna(0).clip(lower=0)
        edit['Custo novo (R$)']=edit['Custo unit. novo (R$)']*edit['Qtd nova']
        edit['Economia (R$)']=edit['Custo atual (R$)']-edit['Custo novo (R$)']
        st.session_state['simulacoes_itens_e60']=edit.drop(columns=['Custo novo (R$)','Economia (R$)']).to_dict('records')
        selecionados=edit.loc[edit['Considerar no cenário'].fillna(False).astype(bool)].copy()
        duplicados=selecionados['Referência'].duplicated(keep=False)
        if duplicados.any():
            st.error('Há alternativas selecionadas para a mesma linha original. Desmarque as alternativas concorrentes para evitar dupla contagem.')
        else:
            total=selecionados['Economia (R$)'].sum()
            x,y,z=st.columns(3)
            x.metric('Economia potencial por ocorrência',f'R$ {total:+.2f}')
            y.metric('Impacto ilustrativo mensal',f'R$ {total*volume:+,.2f}')
            z.metric('Alternativas incluídas',len(selecionados))
            st.caption('Projeção mensal pressupõe que cada ocorrência selecionada corresponde a uma unidade por forno. Confirme a explosão da BOM e o consumo real antes de usar como orçamento.')
        st.dataframe(edit[['Código atual','Descrição atual','Descrição nova','Qtd atual','Qtd nova','Custo atual (R$)','Custo novo (R$)','Economia (R$)','Status','Considerar no cenário']],hide_index=True,use_container_width=True)
        st.download_button('⬇️ Exportar simulações CSV',edit.to_csv(index=False,sep=';',decimal=',').encode('utf-8-sig'),'E60_simulacao_substituicao_itens.csv','text/csv')
        st.caption('As alterações ficam nesta sessão. Exporte o CSV antes de fechar a página; o GitHub não armazena automaticamente os lançamentos.')
    else:
        st.info('Selecione um item acima e adicione uma alternativa para começar.')


# Painel consolidado: não utiliza o potencial genérico dos projetos, evitando contagem dupla.
with abas[8]:
    st.subheader('📈 Painel integrado — itens + cronoanálise')
    st.caption('Custo original × cenário projetado, sem adicionar estimativas genéricas da carteira de projetos.')
    st.warning('Valores de cronoanálise dependem de taxa de custo por hora e multiplicidade por forno. Redução de tempo só vira economia financeira quando a capacidade/custo puder ser efetivamente capturada. Confira a explosão da BOM antes de validar o total.')
    c1,c2,c3=st.columns(3)
    with c1:
        taxa_hora=st.number_input('Custo do recurso (R$/hora)',min_value=0.0,value=0.0,step=5.0,key='taxa_hora_integrado',help='Taxa efetivamente evitável; zero até confirmar com controladoria.')
    with c2:
        so_aprovados=st.checkbox('Considerar somente alternativas aprovadas',value=False,key='aprovados_integrado')
    with c3:
        incluir_crono=st.checkbox('Incluir economia de tempo no cenário',value=True,key='incluir_crono_integrado')
    sims_integradas=pd.DataFrame(st.session_state.get('simulacoes_itens_e60',[]))
    if not sims_integradas.empty:
        sims_integradas=sims_integradas.loc[sims_integradas['Considerar no cenário'].fillna(False).astype(bool)].copy()
        if so_aprovados:
            sims_integradas=sims_integradas.loc[sims_integradas['Status'].eq('Aprovado')].copy()
        refs_duplicadas=sims_integradas['Referência'].duplicated(keep=False).any()
        sims_integradas['Economia calculada (R$)']=pd.to_numeric(sims_integradas['Custo atual (R$)'],errors='coerce').fillna(0)-pd.to_numeric(sims_integradas['Qtd nova'],errors='coerce').fillna(0)*pd.to_numeric(sims_integradas['Custo unit. novo (R$)'],errors='coerce').fillna(0)
    else:
        refs_duplicadas=False
    if refs_duplicadas:
        st.error('Há duas ou mais alternativas selecionadas para a mesma linha. O ganho de itens foi bloqueado até corrigir a duplicidade na aba Simulação de itens.')
    ganho_itens=0.0 if refs_duplicadas or sims_integradas.empty else float(sims_integradas['Economia calculada (R$)'].sum())
    st.markdown('#### Conversão dos tempos em custo')
    tempos_integrados=st.session_state.get('tempos_crono_e60_segundos_descricao_v2',pd.DataFrame())
    ganho_tempo=0.0
    if isinstance(tempos_integrados,pd.DataFrame) and not tempos_integrados.empty:
        cr=tempos_integrados.copy()
        cr['Novo tempo (s)']=pd.to_numeric(cr['Novo tempo (s)'],errors='coerce')
        cr=cr.loc[cr['Novo tempo (s)'].notna()].copy()
        if not cr.empty:
            saved_sel=st.session_state.get('crono_integracao_selecoes_e60',{})
            cr['Multiplicidade por forno']=cr['ID'].astype(str).map(lambda i:saved_sel.get(i,{}).get('Multiplicidade por forno',1.0))
            cr['Considerar']=cr['ID'].astype(str).map(lambda i:saved_sel.get(i,{}).get('Considerar',False))
            chaves=['ID','Conjunto / código','Estágio','Descrição do item','Operação','Tempo padrão (s)','Novo tempo (s)','Multiplicidade por forno','Considerar']
            st.caption('Marque apenas operações confirmadas, informe quantas vezes ocorrem por forno e evite operações que já estejam incluídas no ganho de um item substituído.')
            ed=st.data_editor(cr[chaves],hide_index=True,use_container_width=True,key='editor_integracao_tempos',disabled=['ID','Conjunto / código','Estágio','Descrição do item','Operação','Tempo padrão (s)','Novo tempo (s)'],column_config={'Considerar':st.column_config.CheckboxColumn('Incluir'),'Multiplicidade por forno':st.column_config.NumberColumn(min_value=0.0,step=1.0,format='%.2f')})
            st.session_state['crono_integracao_selecoes_e60']={str(row['ID']):{'Considerar':bool(row['Considerar']),'Multiplicidade por forno':float(row['Multiplicidade por forno'])} for _,row in ed.iterrows()}
            ed=ed.loc[ed['Considerar'].fillna(False).astype(bool)].copy()
            ed['Multiplicidade por forno']=pd.to_numeric(ed['Multiplicidade por forno'],errors='coerce').fillna(0).clip(lower=0)
            ed['Economia tempo (R$)']=(ed['Tempo padrão (s)']-ed['Novo tempo (s)'])*ed['Multiplicidade por forno']*taxa_hora/3600
            if incluir_crono:
                ganho_tempo=float(ed['Economia tempo (R$)'].sum())
            if not ed.empty:
                st.dataframe(ed[['Descrição do item','Estágio','Operação','Multiplicidade por forno','Economia tempo (R$)']],hide_index=True,use_container_width=True)
        else:
            st.info('Preencha os novos tempos na aba Cronoanálise para habilitar o cálculo.')
    else:
        st.info('Ainda não há tempos medidos. Registre-os na aba Cronoanálise.')
    if taxa_hora==0 and incluir_crono:
        st.info('Informe uma taxa horária evitável para transformar os segundos economizados em R$.')
    ganho_total=ganho_itens+ganho_tempo
    custo_projetado=custo-ganho_total
    st.markdown('<div class="gno-strip"><b>RESULTADO OPERACIONAL · CENÁRIO SIMULADO</b><br><small>Comparação entre custo padrão e custo projetado por forno</small></div>',unsafe_allow_html=True)
    chart_comp = pd.DataFrame({'Cenário':['Padrão ERP','Projetado'], 'R$/forno':[custo,custo_projetado]})
    fig_comp = go.Figure(go.Bar(
        x=chart_comp['Cenário'], y=chart_comp['R$/forno'],
        marker_color=['#F15A24','#F15A24'],
        text=[f'R$ {v:,.2f}' for v in chart_comp['R$/forno']],
        textposition='outside', cliponaxis=False,
        hovertemplate='%{x}<br>R$ %{y:,.2f}<extra></extra>'
    ))
    fig_comp.update_layout(template='plotly_white', paper_bgcolor='#FFFFFF', plot_bgcolor='#FFFFFF',
                           font=dict(color='#253244'), showlegend=False, height=310,
                           margin=dict(l=25,r=30,t=35,b=35),
                           yaxis=dict(title='Custo por forno (R$)',gridcolor='#E5E7EB',rangemode='tozero'))
    st.plotly_chart(fig_comp,use_container_width=True)
    st.markdown('#### Indicadores de desempenho econômico')
    a,b,c,d=st.columns(4)
    a.metric('Custo padrão original',f'R$ {custo:,.2f}')
    b.metric('Economia em itens',f'R$ {ganho_itens:+,.2f}')
    c.metric('Economia em processos',f'R$ {ganho_tempo:+,.2f}')
    d.metric('Custo projetado',f'R$ {custo_projetado:,.2f}',delta=f'{-ganho_total:+.2f} R$',delta_color='inverse')
    a,b,c=st.columns(3)
    a.metric('Redução projetada',f'{100*ganho_total/custo:.2f}%' if custo else '—')
    b.metric('Economia mensal',f'R$ {ganho_total*volume:,.2f}')
    c.metric('Economia anual',f'R$ {ganho_total*volume*12:,.2f}')
    if custo_projetado<0:
        st.error('Custo projetado negativo: revise taxas, quantidades e possíveis sobreposições.')
    if ganho_total>0 and volume>0:
        st.metric('Payback simples do investimento informado',f'{investimento/(ganho_total*volume):.1f} meses')
    resumo=pd.DataFrame([{'Custo original (R$/forno)':custo,'Economia itens (R$/forno)':ganho_itens,'Economia crono (R$/forno)':ganho_tempo,'Economia total (R$/forno)':ganho_total,'Custo projetado (R$/forno)':custo_projetado,'Volume mensal':volume,'Economia anual (R$)':ganho_total*volume*12}])
    st.download_button('⬇️ Exportar resumo integrado (CSV)',resumo.to_csv(index=False,sep=';',decimal=',').encode('utf-8-sig'),file_name='E60_painel_integrado.csv',mime='text/csv')
    st.caption('Cenário de estudo, não custo aprovado. Alterações confirmadas são salvas no armazenamento configurado.')

# Salvamento automático após processamento dos editores (sem botão obrigatório).
st.divider()
with st.expander('💾 Salvamento e cópias de segurança', expanded=False):
    st.caption('Armazenamento ativo: '+('Supabase PostgreSQL (nuvem)' if USE_CLOUD else 'SQLite local (não seguro para Streamlit Cloud)')+'. Cada alteração confirmada gera uma versão. Exporte backups JSON periodicamente.')
    if st.session_state.get('_persist_error'):
        st.error('Erro no armazenamento: '+st.session_state['_persist_error'])
    if st.session_state.get('_last_saved_at'):
        st.caption('Último registro (UTC): '+str(st.session_state['_last_saved_at']))
    backup=json.dumps(export_state(),ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
    st.download_button('⬇️ Baixar backup completo (JSON)',backup,'E60_backup_simulacoes.json','application/json')
    arquivo=st.file_uploader('Restaurar backup JSON',type=['json'],key='restaurar_e60_json')
    if arquivo is not None and st.button('Restaurar backup (substitui dados atuais)'):
        try:
            payload=json.loads(arquivo.getvalue().decode('utf-8'))
            if not isinstance(payload,dict) or not set(payload).issubset(set(PERSIST_KEYS)):
                raise ValueError('Formato de backup incompatível')
            restore_state(payload)
            saved_at = save_snapshot(export_state())
            st.session_state['_last_saved_at'] = saved_at
            # Remove cache de editores para refletir dados restaurados.
            for k in ['editor_crono_segundos_descricao_v2','editor_alternativas_e60','editor_integracao_tempos','projetos']:
                st.session_state.pop(k,None)
            st.session_state['_last_persisted']=json.dumps(export_state(),ensure_ascii=False,allow_nan=False)
            st.success('Backup restaurado.')
            st.rerun()
        except Exception as exc:
            st.error(f'Falha ao restaurar: {exc}')
try:
    atual=json.dumps(export_state(),ensure_ascii=False,allow_nan=False)
    if atual != st.session_state.get('_last_persisted'):
        saved_at = save_snapshot(export_state())
        st.session_state['_last_persisted']=atual
        st.session_state['_last_saved_at']=saved_at
except Exception as exc:
    st.error('Não foi possível salvar as alterações: '+str(exc))
