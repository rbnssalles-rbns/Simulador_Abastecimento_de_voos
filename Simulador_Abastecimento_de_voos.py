#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import streamlit as st
import pandas as pd
import easyocr
import re

st.set_page_config(page_title="Simulador de Abastecimento de Voos", layout="wide")

st.title("✈️ Simulador de Abastecimento de Voos")

# Upload do arquivo Excel com estoque e receitas
uploaded_file = st.file_uploader("Carregue o arquivo de estoque e refeições (.xlsx)", type=["xlsx"])

if uploaded_file:
    df_itens = pd.read_excel(uploaded_file, sheet_name="Cadastro de Itens")
    df_refeicoes = pd.read_excel(uploaded_file, sheet_name="Definição de Refeições")

    # Cache para manter estoque atualizado
    if "estoque" not in st.session_state:
        st.session_state.estoque = df_itens.copy()

    st.subheader("📦 Estoque Atual")
    st.dataframe(st.session_state.estoque)

    # Escolha do método de entrada de voos
    metodo = st.radio("Selecione o método de entrada de voos:", ["Excel", "Imagens"])

    df_voos = None

    # --- OPÇÃO 1: Excel ---
    if metodo == "Excel":
        uploaded_voos = st.file_uploader("Carregue programação de voos (.xlsx)", type=["xlsx"])
        if uploaded_voos:
            df_voos = pd.read_excel(uploaded_voos, sheet_name="Programação de Voos")
            st.subheader("🛫 Programação de Voos (Excel)")
            st.dataframe(df_voos)

    # --- OPÇÃO 2: Imagens com EasyOCR ---
    if metodo == "Imagens":
        uploaded_images = st.file_uploader("Carregue imagens dos voos", type=["jpg","jpeg","png"], accept_multiple_files=True)
        if uploaded_images:
            reader = easyocr.Reader(['pt'])
            dados_voos = []
            for img_file in uploaded_images:
                results = reader.readtext(img_file.read())
                texto = " ".join([res[1] for res in results])

                # Parsing automático com regex
                voo = re.search(r"LA\s*\d+", texto) or re.search(r"[A-Z]{2}\d+", texto)
                partida = re.search(r"(\d{2}/\d{2}/\d{4}).*?(\d{2}:\d{2})", texto)
                chegada = re.search(r"ETA.*?(\d{2}/\d{2}/\d{4}).*?(\d{2}:\d{2})", texto)
                rota = re.search(r"[A-Z]{3}\s*-\s*[A-Z]{3}", texto)
                classeA = re.search(r"J\s+(\d+)", texto)
                classeB = re.search(r"Y\s+(\d+)", texto)

                dados_voos.append({
                    "Nº do Voo": voo.group(0) if voo else None,
                    "Data": partida.group(1) if partida else None,
                    "Horário Partida": partida.group(2) if partida else None,
                    "Horário Chegada": chegada.group(2) if chegada else None,
                    "Rota": rota.group(0) if rota else None,
                    "Passageiros Classe A": int(classeA.group(1)) if classeA else 0,
                    "Passageiros Classe B": int(classeB.group(1)) if classeB else 0,
                    "Passageiros Classe C": 0
                })

            df_voos = pd.DataFrame(dados_voos)
            st.subheader("🛫 Programação de Voos (Imagens OCR)")
            st.dataframe(df_voos)

    # --- SIMULAÇÃO EM LOTE ---
    if df_voos is not None and not df_voos.empty:
        st.subheader("🍽️ Simulação de Consumo em Lote")

        regras = {
            "Classe A": {"Refeição Executiva": 1, "Lanche": 0},
            "Classe B": {"Refeição Executiva": 1, "Lanche": 1},
            "Classe C": {"Refeição Executiva": 0, "Lanche": 1},
        }

        consumo_total = []

        for _, voo in df_voos.iterrows():
            passageiros = {
                "Classe A": voo.get("Passageiros Classe A", 0),
                "Classe B": voo.get("Passageiros Classe B", 0),
                "Classe C": voo.get("Passageiros Classe C", 0),
            }

            for classe, qtd in passageiros.items():
                for tipo_ref, vezes in regras[classe].items():
                    for _, row in df_refeicoes[df_refeicoes["Tipo de Refeição"] == tipo_ref].iterrows():
                        consumo_total.append({
                            "ID Item": row["ID Item"],
                            "Item": row["Item"],
                            "Quantidade": row["Quantidade"] * qtd * vezes,
                            "Voo": voo.get("Nº do Voo", "Desconhecido")
                        })

        df_consumo = pd.DataFrame(consumo_total).groupby(["ID Item", "Item"]).sum().reset_index()
        st.dataframe(df_consumo)

        # Atualizar estoque
        for _, row in df_consumo.iterrows():
            st.session_state.estoque.loc[
                st.session_state.estoque["ID"] == row["ID Item"], "Estoque inicial"
            ] -= row["Quantidade"]

        st.success("✅ Estoque atualizado após simulação em lote.")

        # --- RELATÓRIO DE REPOSIÇÃO ---
        st.subheader("📊 Relatório de Reposição")
        limite_minimo = 5000  # exemplo de limite mínimo
        df_reposicao = st.session_state.estoque[st.session_state.estoque["Estoque inicial"] < limite_minimo]
        st.dataframe(df_reposicao)

        if not df_reposicao.empty:
            st.warning("⚠️ É necessário repor os itens listados acima.")
else:
    st.info("Carregue o arquivo Excel de estoque e receitas para iniciar a simulação.")

