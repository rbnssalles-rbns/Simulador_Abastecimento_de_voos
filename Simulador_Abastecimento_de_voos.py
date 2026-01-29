#!/usr/bin/env python
# coding: utf-8

# In[ ]:


#Configuração inicial
import streamlit as st
import pandas as pd
import easyocr
import re

st.set_page_config(page_title="Simulador de Abastecimento de Voos", layout="wide")
st.title("✈️ Simulador de Abastecimento de Voos")
#Função de normalização
def normalizar_consumo(item, quantidade, unidade, embalagem_ml=None):
    if unidade in ["g", "grama", "gramas"]:
        return quantidade / 1000, "kg", None
    elif unidade in ["ml", "mililitro", "mililitros"]:
        litros = quantidade / 1000
        unidades_embalagem = None
        if embalagem_ml:
            unidades_embalagem = int(-(-quantidade // embalagem_ml))  # arredonda para cima
        return litros, "litros", unidades_embalagem
    else:
        return quantidade, unidade, quantidade
#Upload da base de estoque e refeições
uploaded_file = st.file_uploader("Carregue o arquivo de estoque e refeições (.xlsx)", type=["xlsx"])

if uploaded_file:
    df_itens = pd.read_excel(uploaded_file, sheet_name="Cadastro de Itens")
    df_refeicoes = pd.read_excel(uploaded_file, sheet_name="Definição de Refeições")

    if "estoque" not in st.session_state:
        st.session_state.estoque = df_itens.copy()

    st.subheader("📦 Estoque Atual")
    st.dataframe(st.session_state.estoque)
#Reposição de estoque
    uploaded_reposicao = st.file_uploader("Carregue arquivo de reposição de estoque (.xlsx)", type=["xlsx"])
    if uploaded_reposicao:
        df_reposicao = pd.read_excel(uploaded_reposicao, sheet_name="Reposição")
        st.subheader("📥 Itens de Reposição")
        st.dataframe(df_reposicao)

        for _, row in df_reposicao.iterrows():
            item_id = row["ID"]
            item_nome = row["Item"]
            unidade = str(row["Unidade"]).lower()
            qtd_reposta = row["Quantidade Reposta"]

            if unidade in ["ton", "tonelada", "toneladas"]:
                qtd_reposta = qtd_reposta * 1000
                unidade = "kg"

            if item_id in st.session_state.estoque["ID"].values:
                st.session_state.estoque.loc[
                    st.session_state.estoque["ID"] == item_id, "Estoque inicial"
                ] += qtd_reposta
                st.session_state.estoque.loc[
                    st.session_state.estoque["ID"] == item_id, "Unidade"
                ] = unidade
            else:
                novo_item = {
                    "ID": item_id,
                    "Item": item_nome,
                    "Unidade": unidade,
                    "Estoque inicial": qtd_reposta
                }
                st.session_state.estoque = pd.concat(
                    [st.session_state.estoque, pd.DataFrame([novo_item])],
                    ignore_index=True
                )

        st.success("✅ Estoque atualizado com a reposição.")
        st.subheader("📦 Estoque Atualizado")
        st.dataframe(st.session_state.estoque)
#Entrada de voos (Excel ou Imagem OCR)
    metodo = st.radio("Selecione o método de entrada de voos:", ["Excel", "Imagens"])
    df_voos = None

    if metodo == "Excel":
        uploaded_voos = st.file_uploader("Carregue programação de voos (.xlsx)", type=["xlsx"])
        if uploaded_voos:
            df_voos = pd.read_excel(uploaded_voos, sheet_name="Programação de Voos")
            st.subheader("🛫 Programação de Voos (Excel)")
            st.dataframe(df_voos)

    if metodo == "Imagens":
        uploaded_images = st.file_uploader("Carregue imagens dos voos", type=["jpg","jpeg","png"], accept_multiple_files=True)
        if uploaded_images:
            reader = easyocr.Reader(['pt'])
            dados_voos = []
            for img_file in uploaded_images:
                results = reader.readtext(img_file.read())
                texto = " ".join([res[1] for res in results])
                st.text_area("Texto extraído da imagem", texto, height=200)

                voo = re.search(r"(LA|TP|G3)\s*\d{3,4}", texto)
                classeA = re.search(r"J\s+(\d{1,3})", texto)
                classeB = re.search(r"Y\s+(\d{1,3})", texto)

                dados_voos.append({
                    "Nº do Voo": voo.group(0) if voo else None,
                    "Passageiros Classe A": int(classeA.group(1)) if classeA else 0,
                    "Passageiros Classe B": int(classeB.group(1)) if classeB else 0,
                    "Passageiros Classe C": 0
                })

            df_voos = pd.DataFrame(dados_voos)
            st.subheader("🛫 Programação de Voos (Imagens OCR)")
            st.dataframe(df_voos)
    # --- SIMULAÇÃO INDIVIDUAL POR VOO ---
    # --- SIMULAÇÃO INDIVIDUAL POR VOO ---
    # --- BLOCO 6: SIMULAÇÃO DE CONSUMO, CACHE E REPOSIÇÃO ---
if "estoque_cache" not in st.session_state:
    st.session_state.estoque_cache = st.session_state.estoque.copy()

if "historico_voos" not in st.session_state:
    st.session_state.historico_voos = []

if df_voos is not None and not df_voos.empty:
    st.subheader("🍽️ Simulação de Consumo por Voo")

    for _, voo in df_voos.iterrows():
        consumo_voo = {}

        passageiros = {
            "Classe A": int(voo.get("Passageiros Classe A", 0)),
            "Classe B": int(voo.get("Passageiros Classe B", 0)),
            "Classe C": int(voo.get("Passageiros Classe C", 0)),
        }

        # cálculo por classe usando Definição de Refeições
        for classe, qtd_pax in passageiros.items():
            if qtd_pax == 0:
                continue
            for _, item in df_refeicoes.iterrows():
                coluna_quantidade = f"Quantidade Classe {classe[-1]}"
                quantidade_por_pax = item.get(coluna_quantidade, 0)
                if quantidade_por_pax == 0:
                    continue
                key = (item["ID Item"], item["Item"])
                if key not in consumo_voo:
                    consumo_voo[key] = 0
                consumo_voo[key] += quantidade_por_pax * qtd_pax

        # DataFrame consolidado do voo
        df_consumo_voo = pd.DataFrame([
            {
                "ID Item": k[0],
                "Item": k[1],
                "Voo": voo["Nº do Voo"],
                "Quantidade": v
            } for k, v in consumo_voo.items()
        ])

        # Atualiza cache de estoque
        estoque = st.session_state.estoque_cache
        for _, row in df_consumo_voo.iterrows():
            if row["ID Item"] in estoque["ID"].values:
                estoque.loc[
                    estoque["ID"] == row["ID Item"], "Estoque Inicial"
                ] -= row["Quantidade"]

        # Checagem de reposição
        limite_minimo = 5
        itens_faltando = estoque[estoque["Estoque Inicial"] < limite_minimo]
        if not itens_faltando.empty:
            st.warning(f"⚠️ Estoque crítico após voo {voo['Nº do Voo']}. Reposição necessária.")
            if "df_reposicao" in locals() and df_reposicao is not None and not df_reposicao.empty:
                for _, row in df_reposicao.iterrows():
                    if row["ID Item"] in estoque["ID"].values:
                        estoque.loc[
                            estoque["ID"] == row["ID Item"], "Estoque Inicial"
                        ] += row["Quantidade Reposta"]
                st.success("✅ Reposição aplicada automaticamente!")

        # Guarda histórico do voo
        st.session_state.historico_voos.append({
            "Voo": voo["Nº do Voo"],
            "Data": voo["Data"],
            "Consumo": df_consumo_voo,
            "Saldo Atualizado": estoque.copy()
        })

        # Exibe consumo individual
        st.subheader(f"🍽️ Consumo do Voo {voo['Nº do Voo']}")
        st.dataframe(df_consumo_voo)

# --- RELATÓRIO CONSOLIDADO DE VOOS ---
if st.session_state.historico_voos:
    st.subheader("📊 Relatório Consolidado de Voos")
    relatorio = []
    for registro in st.session_state.historico_voos:
        for _, row in registro["Consumo"].iterrows():
            relatorio.append({
                "Voo": registro["Voo"],
                "Data": registro["Data"],
                "Item": row["Item"],
                "Quantidade Consumida": row["Quantidade"],
                "Saldo Final": registro["Saldo Atualizado"].loc[
                    registro["Saldo Atualizado"]["ID"] == row["ID Item"], "Estoque Inicial"
                ].values[0]
            })
    df_relatorio = pd.DataFrame(relatorio)
    st.dataframe(df_relatorio)

    

