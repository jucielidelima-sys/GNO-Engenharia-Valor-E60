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
            chaves=['ID','Conjunto / código','Descrição do item','Operação','Tempo padrão (s)','Novo tempo (s)','Multiplicidade por forno','Considerar']
            st.caption('Marque apenas operações confirmadas, informe quantas vezes ocorrem por forno e evite operações que já estejam incluídas no ganho de um item substituído.')
            ed=st.data_editor(cr[chaves],hide_index=True,use_container_width=True,key='editor_integracao_tempos',disabled=['ID','Conjunto / código','Descrição do item','Operação','Tempo padrão (s)','Novo tempo (s)'],column_config={'Considerar':st.column_config.CheckboxColumn('Incluir'),'Multiplicidade por forno':st.column_config.NumberColumn(min_value=0.0,step=1.0,format='%.2f')})
            st.session_state['crono_integracao_selecoes_e60']={str(row['ID']):{'Considerar':bool(row['Considerar']),'Multiplicidade por forno':float(row['Multiplicidade por forno'])} for _,row in ed.iterrows()}
            ed=ed.loc[ed['Considerar'].fillna(False).astype(bool)].copy()
            ed['Multiplicidade por forno']=pd.to_numeric(ed['Multiplicidade por forno'],errors='coerce').fillna(0).clip(lower=0)
            ed['Economia tempo (R$)']=(ed['Tempo padrão (s)']-ed['Novo tempo (s)'])*ed['Multiplicidade por forno']*taxa_hora/3600
            if incluir_crono:
                ganho_tempo=float(ed['Economia tempo (R$)'].sum())
            if not ed.empty:
                st.dataframe(ed[['Descrição do item','Operação','Multiplicidade por forno','Economia tempo (R$)']],hide_index=True,use_container_width=True)
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
