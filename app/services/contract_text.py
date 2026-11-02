"""Texto do contrato padrão da EMG: Contrato de Prestação de Serviços de Consultoria para Estruturação e
Captação de Crédito (modelo H2 Fibra, com a EMG como CONTRATADA).

Campos variáveis: qualificação da CONTRATANTE, tarifa de estruturação e forma de pagamento.
As demais cláusulas são fixas. Marcação: <b>...</b> para negrito (reportlab Paragraph).
"""
from __future__ import annotations

from ..config import settings
from ..utils import brl, extenso_reais

TITULO = "CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE CONSULTORIA<br/>PARA ESTRUTURAÇÃO E CAPTAÇÃO DE CRÉDITO"

TABELA_EXITO = [
    ("Sobre a parcela de até R$ 500.000,00", "15% (quinze por cento)"),
    ("Sobre a parcela que exceder R$ 500.000,00", "10% (dez por cento)"),
]


def _nome_contratante(c) -> str:
    nome = c.razao_social.upper()
    if getattr(c, "nome_fantasia", None):
        nome += f" (nome fantasia {c.nome_fantasia.upper()})"
    return nome


def _endereco_contratante(c) -> str:
    partes = [p for p in [c.endereco, c.cidade_uf] if p]
    txt = ", ".join(partes)
    if c.cep:
        txt += f", CEP {c.cep}"
    return txt


def preambulo(c) -> str:
    end = _endereco_contratante(c)
    return (
        f"Pelo presente instrumento particular, de um lado <b>{settings.EMG_RAZAO}</b>, inscrita no CNPJ sob o nº "
        f"{settings.EMG_CNPJ}, com sede na {settings.EMG_ENDERECO}, neste ato representada na forma de seus atos "
        f"constitutivos, doravante denominada <b>CONTRATADA</b>; e, de outro lado, <b>{_nome_contratante(c)}</b>, "
        f"inscrita no CNPJ sob o nº {c.cnpj}" + (f", com sede na {end}" if end else "") +
        f", neste ato representada por seu representante legal <b>{c.representante.upper()}</b>, portador(a) do CPF nº "
        f"{c.representante_cpf}, doravante denominada <b>CONTRATANTE</b>; têm entre si justo e contratado o seguinte:"
    )


def clausulas(c) -> list[tuple[str, list[str]]]:
    tarifa = brl(c.tarifa_valor)
    tarifa_ext = extenso_reais(c.tarifa_valor)
    forma = c.forma_pagamento.strip().rstrip(".")
    return [
        ("CLÁUSULA 1ª · OBJETO", [
            "1.1. Prestação, pela <b>CONTRATADA</b>, de serviços de <b>consultoria em estruturação e captação de crédito</b>, compreendendo: (a) diagnóstico econômico-financeiro e análise do perfil de crédito da <b>CONTRATANTE</b>, inclusive mediante leitura de relatórios do Sistema de Informações de Crédito do Banco Central (SCR/Registrato) fornecidos pela <b>CONTRATANTE</b>; (b) definição da estratégia de captação, das linhas e das instituições financeiras adequadas a cada demanda; (c) elaboração e organização de consultas prévias, projetos e dossiês de crédito nos formatos exigidos por cada instituição; (d) condução e acompanhamento dos pleitos junto às instituições até a decisão final; e (e) orientação de procedimentos contábeis e cadastrais, excluídos os lançamentos contábeis em si.",
            "1.2. Os serviços constituem <b>obrigação de meio</b>. A <b>CONTRATADA não garante aprovação, prazo ou volume de crédito</b>, decisões que competem exclusivamente às instituições financeiras.",
        ]),
        ("CLÁUSULA 2ª · PRAZO DE EXECUÇÃO E VIGÊNCIA", [
            "2.1. A fase ativa da consultoria será executada no prazo de até <b>90 (noventa) dias</b> contados da entrega, pela <b>CONTRATANTE</b>, da totalidade da documentação solicitada.",
            "2.2. Este contrato vigorará por <b>24 (vinte e quatro) meses</b> a contar da assinatura, prorrogando-se automaticamente por igual período salvo manifestação escrita de qualquer das partes com <b>60 (sessenta) dias</b> de antecedência. A vigência de 24 (vinte e quatro) meses destina-se, em especial, a reger os honorários de êxito sobre liberações que ocorram após a fase ativa, nos termos da Cláusula 3ª.",
        ]),
        ("CLÁUSULA 3ª · HONORÁRIOS DE ÊXITO", [
            "3.1. Pelos serviços, a <b>CONTRATANTE</b> pagará à <b>CONTRATADA honorários de êxito</b> calculados de forma <b>progressiva</b> sobre cada valor liberado, conforme a tabela:",
            "__TABELA_EXITO__",
            "3.2. Consideram-se devidos os honorários sobre <b>todo crédito liberado, contratado ou disponibilizado durante a vigência deste contrato</b> em favor da <b>CONTRATANTE</b>, de suas filiais, de empresas do mesmo grupo econômico ou de seus sócios, quando decorrente de pleito, projeto, estratégia ou instituição financeira apresentados, estruturados ou acionados pela <b>CONTRATADA</b>, ainda que: (a) a liberação ocorra após o encerramento da fase ativa de 90 dias; (b) o desembolso se dê diretamente a terceiros, como nos financiamentos de bens e demais linhas sem crédito em conta da <b>CONTRATANTE</b>; ou (c) a formalização final seja concluída pela própria <b>CONTRATANTE</b> diretamente com a instituição.",
            "3.2.1. Para os fins deste contrato, considera-se <b>crédito</b> toda e qualquer modalidade de operação, linha ou limite concedido por instituição financeira ou sociedade de crédito, incluindo, sem se limitar a: empréstimos e financiamentos em geral, capital de giro, crédito com garantia de imóvel, veículo ou recebíveis, financiamento de bens e equipamentos, <b>cartão de crédito, inclusive concessão ou majoração de limite</b>, cheque especial, limite de conta e conta garantida, antecipação de recebíveis, desconto de títulos, arrendamento mercantil (leasing), fiança e aval bancário, carta de crédito e linhas de fomento ou com garantia de fundos públicos (BNDES, FGI, Pronampe e similares).",
            "3.2.2. Nas linhas rotativas ou de limite (cartão de crédito, cheque especial, limite de conta, conta garantida e similares), os honorários incidem sobre o <b>valor do limite concedido ou majorado</b>, devidos no ato da disponibilização, independentemente da efetiva utilização do limite pela <b>CONTRATANTE</b>.",
            "3.3. O pagamento será realizado em até <b>24 (vinte e quatro) horas</b> contadas de cada liberação, por transferência à conta indicada pela <b>CONTRATADA</b>, acompanhado do comprovante da operação de crédito. A <b>CONTRATANTE</b> autoriza a <b>CONTRATADA</b> a confirmar as liberações junto à instituição financeira.",
            "3.4. O atraso no pagamento sujeita a <b>CONTRATANTE</b> a <b>multa de 2% (dois por cento)</b>, juros de <b>1% (um por cento) ao mês</b> pro rata die e atualização pelo IPCA, além de honorários advocatícios de 20% (vinte por cento) em caso de cobrança judicial ou extrajudicial.",
            f"3.5. <b>Tarifa de estruturação</b>: pela abertura do dossiê, análise documental e diagnóstico, a <b>CONTRATANTE</b> pagará à <b>CONTRATADA</b> o valor de <b>{tarifa} ({tarifa_ext})</b>, devido no ato da assinatura, mediante {forma}, e não reembolsável, salvo o disposto na Cláusula 5ª.",
            "3.6. Não haverá devolução de valores nem afastamento dos honorários quando a negativa ou a redução do crédito decorrer de omissão de informações, documentação incompleta, restritivos internos ou externos da <b>CONTRATANTE</b> ou de seus sócios, ou de desistência da operação pela <b>CONTRATANTE</b>.",
        ]),
        ("CLÁUSULA 4ª · OBRIGAÇÕES DAS PARTES", [
            "4.1. A <b>CONTRATANTE</b> obriga-se a: (a) fornecer com exatidão e tempestividade todas as informações e documentos solicitados; (b) obter e entregar os relatórios do Registrato/SCR de sua titularidade quando solicitados; (c) comunicar à <b>CONTRATADA</b>, em até <b>48 (quarenta e oito) horas</b>, qualquer contato, proposta ou liberação recebida de instituição financeira relacionada aos pleitos em curso; e (d) <b>não negociar diretamente</b>, durante a vigência, os pleitos estruturados pela <b>CONTRATADA</b> sem a sua participação.",
            "4.2. A <b>CONTRATADA</b> obriga-se a: (a) manter sigilo absoluto sobre dados, documentos e informações da <b>CONTRATANTE</b>; (b) conduzir os pleitos com diligência e reportar o andamento; e (c) responder pelas subcontratações que realizar para o objeto principal deste contrato.",
        ]),
        ("CLÁUSULA 5ª · RESCISÃO", [
            "5.1. Qualquer das partes poderá rescindir mediante aviso escrito de <b>30 (trinta) dias</b>.",
            f"5.2. Rescisão pela <b>CONTRATANTE</b>: (a) antes do envio de qualquer pleito às instituições, ficará devida apenas a tarifa de estruturação da cláusula 3.5; caso esta tenha sido isentada ou ainda não paga, ficará devido, a título compensatório, valor a ela equivalente, de <b>{tarifa} ({tarifa_ext})</b>; (b) após o envio de pleito a qualquer instituição, permanecerão devidos os honorários de êxito da Cláusula 3ª sobre as liberações que vierem a ocorrer no prazo de <b>24 (vinte e quatro) meses</b> decorrentes dos pleitos enviados.",
            "5.3. O contrato estará automaticamente rescindido em caso de falência, recuperação judicial ou extrajudicial de qualquer das partes, ou descumprimento grave de suas cláusulas, sem prejuízo dos honorários já devidos.",
        ]),
        ("CLÁUSULA 6ª · NÃO EXCLUSIVIDADE", [
            "6.1. A <b>CONTRATADA</b> poderá prestar serviços a terceiros, inclusive do mesmo segmento da <b>CONTRATANTE</b>, resguardado o sigilo de cada cliente.",
        ]),
        ("CLÁUSULA 7ª · PROTEÇÃO DE DADOS", [
            "7.1. As partes cumprirão a Lei nº 13.709/2018 (LGPD), tratando os dados pessoais a que tiverem acesso exclusivamente para a execução deste contrato, com medidas de segurança adequadas, comunicação de incidentes em até 48 (quarenta e oito) horas e eliminação ou devolução dos dados ao término da relação, salvo base legal para retenção.",
            "7.2. A <b>CONTRATANTE</b> declara e autoriza, de forma específica, o tratamento pela <b>CONTRATADA</b> dos dados financeiros e de crédito seus e de seus sócios, inclusive relatórios do Registrato/SCR por ela fornecidos, para os fins deste contrato.",
        ]),
        ("CLÁUSULA 8ª · CONFIDENCIALIDADE E ANTICORRUPÇÃO", [
            "8.1. As informações trocadas em razão deste contrato são confidenciais e assim permanecerão mesmo após o seu término, respondendo o infrator por perdas e danos.",
            "8.2. As partes declaram conhecer e se obrigam a cumprir a legislação anticorrupção brasileira, em especial as Leis nº 8.429/1992 e nº 12.846/2013, constituindo a sua violação causa de rescisão unilateral.",
        ]),
        ("CLÁUSULA 9ª · DISPOSIÇÕES GERAIS E FORO", [
            "9.1. Alterações somente por termo aditivo assinado pelas partes. A tolerância não implica novação. Este contrato obriga as partes e seus sucessores.",
            "9.2. <b>Assinatura eletrônica</b>: as partes reconhecem como válida e eficaz a assinatura deste contrato por meio eletrônico, em plataforma de assinatura digital, nos termos do art. 10, § 2º, da MP nº 2.200-2/2001 e da Lei nº 14.063/2020, conferindo-lhe plena validade jurídica e força de título executivo extrajudicial, dispensada a assinatura de testemunhas.",
            "9.3. Fica eleito o foro da Comarca do Recife/PE, com renúncia a qualquer outro.",
        ]),
    ]


def qualificacao_contratante(c) -> list[str]:
    linhas = [f"<b>Razão social:</b> {_nome_contratante(c)} · <b>CNPJ:</b> {c.cnpj}"]
    end = _endereco_contratante(c)
    if end:
        linhas.append(f"<b>Endereço:</b> {end}")
    linhas.append(f"<b>Representante:</b> {c.representante.upper()} · <b>CPF:</b> {c.representante_cpf}")
    extras = []
    if c.telefone:
        extras.append(f"<b>Telefone:</b> {c.telefone}")
    if c.email:
        extras.append(f"<b>E-mail:</b> {c.email}")
    if extras:
        linhas.append(" · ".join(extras))
    return linhas
