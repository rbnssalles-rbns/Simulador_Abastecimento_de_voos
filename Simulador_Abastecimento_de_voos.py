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
    if df_voos is not None and not df_voos.empty:
        st.subheader("🍽️ Simulação de Consumo por Voo")

        regras = {
            "Classe A": {"Refeição Executiva": 1, "Lanche": 0},
            "Classe B": {"Refeição Executiva": 1, "Lanche": 1},
            "Classe C": {"Refeição Executiva": 0, "Lanche": 1},
        }

        for _, voo in df_voos.iterrows():
            consumo_voo = []
            passageiros = {
                "Classe A": voo.get("Passageiros Classe A", 0),
                "Classe B": voo.get("Passageiros Classe B", 0),
                "Classe C": voo.get("Passageiros Classe C", 0),
            }

            # cálculo de consumo por classe e refeição
            for classe, qtd in passageiros.items():
                for tipo_ref, vezes in regras[classe].items():
                    for _, row in df_refeicoes[df_refeicoes["Tipo de Refeição"] == tipo_ref].iterrows():
                        consumo_voo.append({
                            "ID Item": row["ID Item"],
                            "Item": row["Item"],
                            "Quantidade": row["Quantidade"] * qtd * vezes,
                            "Voo": voo.get("Nº do Voo", "Desconhecido")
                        })

            df_consumo_voo = pd.DataFrame(consumo_voo).groupby(["ID Item", "Item"]).sum().reset_index()

            # criar mapa de unidades para evitar KeyError
            map_unidades = dict(zip(st.session_state.estoque["ID"], st.session_state.estoque["Unidade"]))

            # normalizar unidades e calcular embalagens
            df_consumo_voo[["Quantidade Normalizada", "Unidade", "Unidades Embalagem"]] = df_consumo_voo.apply(
                lambda row: pd.Series(normalizar_consumo(
                    row["Item"],
                    row["Quantidade"],
                    map_unidades.get(row["ID Item"], "un"),  # fallback seguro
                    embalagem_ml=350 if row["Item"] == "Refrigerante" else None
                )),
                axis=1
            )

            st.subheader(f"🍽️ Consumo do Voo {voo.get('Nº do Voo', 'Desconhecido')}")
            st.dataframe(df_consumo_voo)

            # atualizar estoque
            for _, row in df_consumo_voo.iterrows():
                if row["ID Item"] in map_unidades:  # só atualiza se existir no estoque
                    st.session_state.estoque.loc[
                        st.session_state.estoque["ID"] == row["ID Item"], "Estoque inicial"
                    ] -= row["Quantidade"]

        # --- RELATÓRIO DE REPOSIÇÃO ---
        st.subheader("📊 Relatório de Reposição")
        limite_minimo = 5
        df_reposicao = st.session_state.estoque[st.session_state.estoque["Estoque inicial"] < limite_minimo]
        st.dataframe(df_reposicao)

        if not df_reposicao.empty:
            st.warning("⚠️ É necessário repor os itens listados acima.")

