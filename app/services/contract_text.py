"""Texto do contrato padrão de consultoria de crédito da EMG.

Baseado no modelo "Contrato_EMG_Credito_Inteligente" (Google Docs do Guilherme), sem a cláusula de condições
especiais (que era específica de um cliente). Campos variáveis: qualificação do cliente, tarifa e forma de pagamento.
"""
from __future__ import annotations

from ..config import settings
from ..utils import brl, extenso_reais

TITULO = "CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE CONSULTORIA FINANCEIRA"
SUBTITULO = "COM HONORÁRIOS DE ÊXITO, CONFISSÃO DE DÍVIDA E CLÁUSULAS DE COMPLIANCE"

TABELA_EXITO = [
    ("Até R$ 200.000,00", "15% (quinze por cento)"),
    ("De R$ 200.000,01 até R$ 500.000,00", "10% (dez por cento)"),
    ("De R$ 500.000,01 até R$ 1.499.999,99", "6% (seis por cento)"),
    ("Igual ou superior a R$ 1.500.000,00", "5% (cinco por cento)"),
]


def qualificacao_contratada() -> list[tuple[str, str]]:
    return [
        ("Razão Social", settings.EMG_RAZAO),
        ("Nome Fantasia", settings.EMG_FANTASIA),
        ("CNPJ", settings.EMG_CNPJ),
        ("Endereço", settings.EMG_ENDERECO),
        ("Representante Legal", settings.EMG_REPRESENTANTE),
        ("CPF da Representante", settings.EMG_REPRESENTANTE_CPF),
        ("E-mail", settings.EMG_EMAIL),
        ("Telefone", settings.EMG_TELEFONE),
        ("PIX (pagamento)", settings.EMG_PIX),
    ]


def qualificacao_contratante(c) -> list[tuple[str, str]]:
    return [
        ("Nome / Razão Social", c.razao_social),
        ("CPF / CNPJ", c.cnpj),
        ("RG / IE", c.ie_rg or ""),
        ("Endereço completo", c.endereco or ""),
        ("CEP", c.cep or ""),
        ("Cidade/UF", c.cidade_uf or ""),
        ("Telefone", c.telefone or ""),
        ("E-mail", c.email),
        ("Representante Legal", c.representante),
        ("CPF do Representante", c.representante_cpf),
    ]


def clausulas(c) -> list[tuple[str, list[str]]]:
    tarifa = brl(c.tarifa_valor)
    tarifa_ext = extenso_reais(c.tarifa_valor)
    forma = c.forma_pagamento
    return [
        ("CLÁUSULA PRIMEIRA – OBJETO DO CONTRATO", [
            "1.1. A CONTRATADA obriga-se a prestar serviços de consultoria financeira, compreendendo: análise do perfil financeiro do CONTRATANTE, identificação das melhores modalidades de crédito disponíveis no mercado, estruturação e preparação da documentação necessária, intermediação junto a instituições financeiras parceiras e acompanhamento do processo até a efetiva liberação do crédito.",
            "1.2. As modalidades de crédito passíveis de contratação incluem, de forma exemplificativa e não taxativa: financiamento imobiliário, financiamento veicular, capital de giro, cartão de crédito empresarial, cheque especial, antecipação de recebíveis, crédito com garantia e outras linhas de crédito adequadas ao perfil do CONTRATANTE.",
            "1.3. A definição da modalidade de crédito a ser trabalhada poderá ocorrer após análise técnica do perfil do CONTRATANTE, sendo tal definição prerrogativa da CONTRATADA orientada ao melhor resultado para o cliente.",
            "1.4. A CONTRATADA não atua como instituição financeira, não concede crédito diretamente e não garante aprovação por parte de terceiros. Sua obrigação é de meio, não de resultado.",
        ]),
        ("CLÁUSULA SEGUNDA – HONORÁRIOS INICIAIS DE CONSULTORIA E ANÁLISE", [
            "2.1. O pagamento dos honorários iniciais não se confunde com os honorários de êxito previstos na cláusula seguinte, os quais serão devidos adicionalmente quando configuradas as hipóteses de incidência estabelecidas neste contrato.",
            "2.2. Os honorários iniciais previstos nesta cláusula são devidos de forma obrigatória e independente do resultado da análise ou da aprovação, reprovação, concessão ou efetiva liberação de qualquer modalidade de crédito. Assim, a eventual não aprovação de crédito por instituição financeira não afastará, reduzirá ou dará direito à restituição, total ou parcial, dos honorários iniciais, uma vez que estes remuneram os serviços efetivamente contratados e prestados, independentemente do resultado final.",
            f"2.3. Pela prestação dos serviços iniciais de consulta e análise de crédito, levantamento, organização e conferência de documentação, bem como pelos serviços de natureza contábil e jurídica relacionados à preparação e estruturação do processo de crédito, o CONTRATANTE pagará à CONTRATADA honorários iniciais no valor de {tarifa} ({tarifa_ext}).",
            f"2.4. Forma de pagamento dos honorários iniciais: {forma}. Os pagamentos somente serão válidos quando realizados pela forma de pagamento informada pela CONTRATADA.",
            "2.5. O atraso no pagamento de qualquer parcela dos honorários iniciais acarretará, independentemente de notificação, a incidência de multa moratória de 10% (dez por cento) sobre o valor em atraso, acrescida de juros de mora de 1% (um por cento) ao mês, calculados pro rata die até a data do efetivo pagamento.",
        ]),
        ("CLÁUSULA TERCEIRA – HONORÁRIOS DE ÊXITO", [
            "3.1. A remuneração da CONTRATADA adota o modelo de honorários de êxito: os valores somente serão devidos quando da efetiva liberação, aprovação ou disponibilização do crédito pela instituição financeira, independentemente da modalidade contratada.",
            "3.2. Para os fins deste contrato, considera-se \"efetiva liberação\" a ocorrência de qualquer das seguintes situações, isolada ou cumulativamente: (i) o depósito ou crédito do valor na conta do CONTRATANTE ou de terceiro por ele indicado; (ii) a disponibilização de limite de crédito, cartão de crédito, cheque especial ou qualquer linha de crédito rotativo; (iii) a aprovação formal pela instituição financeira com emissão de contrato, carta de crédito ou documento equivalente, ainda que o CONTRATANTE não realize o saque ou a utilização dos recursos; (iv) a assinatura de contrato de financiamento ou operação de crédito junto à instituição financeira.",
            "3.3. Os honorários incidem sobre o valor total do crédito efetivamente liberado, observados os percentuais da tabela abaixo, sem cálculo progressivo por faixas.",
            "__TABELA_EXITO__",
            "3.4. Os percentuais indicados na tabela incidem de forma integral sobre a base de cálculo aplicável, sem cálculo progressivo por faixas.",
            "3.5. Quando houver mais de uma liberação de crédito, deverá ser observado o intervalo de dias úteis entre cada liberação, contado de uma liberação para a seguinte.",
            "3.6. Caso sejam realizadas duas ou mais liberações de crédito com intervalo de até 03 (três) dias úteis entre uma e outra, os valores das liberações ocorridas dentro desse intervalo serão somados para fins de enquadramento na tabela de honorários, aplicando-se um único percentual sobre o valor total acumulado.",
            "3.7. Caso a nova liberação ocorra após intervalo superior a 03 (três) dias úteis contado da liberação anterior, cada liberação será considerada individualmente para fins de incidência dos honorários, aplicando-se o percentual correspondente sobre o valor de cada crédito liberado.",
            "3.8. Para fins desta cláusula, a contagem dos dias úteis observará o calendário aplicável à localidade da prestação dos serviços, excluindo-se sábados, domingos e feriados.",
            "3.9. O CONTRATANTE reconhece que os honorários são devidos no ato da liberação do crédito, sendo o pagamento condição essencial para continuidade do acesso aos recursos.",
        ]),
        ("CLÁUSULA QUARTA – CONFISSÃO DE DÍVIDA", [
            "4.1. O CONTRATANTE confessa, reconhece e declara expressamente que, no momento em que ocorrer a efetiva liberação de crédito em seu favor, decorrente dos serviços prestados pela CONTRATADA, nascerá de forma automática e incondicional uma dívida líquida, certa e exigível em favor da CONTRATADA, equivalente ao percentual de honorários incidente sobre o valor total do crédito liberado, conforme tabela da Cláusula Terceira.",
            "4.2. A presente Confissão de Dívida constitui título executivo extrajudicial, nos termos do art. 784, inciso III, do Código de Processo Civil Brasileiro (Lei nº 13.105/2015), autorizando a CONTRATADA a promover imediatamente a execução judicial do valor confessado, independentemente de notificação prévia, em caso de inadimplemento.",
            "4.3. O CONTRATANTE declara que: (i) compreende integralmente a natureza e os efeitos jurídicos desta Confissão de Dívida; (ii) assina livre e voluntariamente, sem coação ou vício de consentimento; (iii) possui plena capacidade civil e jurídica para assumir tal obrigação.",
            "4.4. Em caso de inadimplemento, o valor da dívida será corrigido pelo IPCA a partir do vencimento, acrescido de juros de mora de 1% (um por cento) ao mês, multa contratual de 10% (dez por cento) sobre o total em atraso, além de honorários advocatícios fixados desde já em 20% (vinte por cento) sobre o valor total da dívida atualizada, sem prejuízo das custas judiciais.",
            "4.5. O CONTRATANTE autoriza expressamente o protesto extrajudicial deste instrumento junto ao cartório competente em caso de inadimplemento superior a 05 (cinco) dias úteis.",
            "4.6. O registro desta Confissão de Dívida é vinculado ao Anexo I – Registro de Créditos Liberados, que integra este contrato e descreverá, a cada liberação, o valor do crédito, a modalidade, a instituição financeira, o valor dos honorários devidos e a data de vencimento.",
            "4.7. A presente Confissão de Dívida é IRREVOGÁVEL e IRRETRATÁVEL, não podendo ser anulada, revogada ou desconstituída pelo CONTRATANTE unilateralmente, mesmo em caso de rescisão contratual, arrependimento ou alegação de desconhecimento, permanecendo em vigor até a integral quitação dos valores devidos.",
        ]),
        ("CLÁUSULA QUINTA – COMPLIANCE, PREVENÇÃO À LAVAGEM DE DINHEIRO E PROTEÇÃO INSTITUCIONAL", [
            "ATENÇÃO: O descumprimento das obrigações desta cláusula configura rescisão imediata do contrato, sem prejuízo de responsabilidade civil e comunicação aos órgãos competentes.",
            "5.1. O CONTRATANTE declara, sob as penas da lei, que: (a) todas as informações, documentos e dados fornecidos à CONTRATADA são verdadeiros, completos e de origem lícita; (b) os recursos decorrentes do crédito a ser obtido têm origem e destinação lícitas, não se relacionando a qualquer atividade ilegal, criminosa ou vedada por lei; (c) não é, nem representa, interposta pessoa (laranja) de terceiros, agindo exclusivamente em nome próprio e por conta própria; (d) não está sujeito a sanções, bloqueios ou restrições por parte de órgãos reguladores nacionais ou internacionais, incluindo COAF, Banco Central do Brasil, Receita Federal, OFAC ou similares; (e) não possui envolvimento, direto ou indireto, com atividades de lavagem de dinheiro, financiamento ao terrorismo, corrupção, evasão fiscal ou qualquer outro crime financeiro tipificado na legislação brasileira, em especial na Lei nº 9.613/1998 e suas alterações; (f) não atua como beneficiário final de terceiros que não queiram se identificar perante as instituições financeiras; (g) o crédito pleiteado não se destina à ocultação, dissimulação ou integração de recursos de origem ilícita na economia.",
            "5.2. A CONTRATADA reserva-se o direito de recusar, suspender ou encerrar os serviços, a qualquer tempo e sem qualquer ônus, caso identifique ou suspeite, com base em elementos objetivos, da prática de qualquer das condutas descritas no item 5.1, sem que tal recusa gere qualquer direito de indenização ao CONTRATANTE.",
            "5.3. Em cumprimento à Lei nº 9.613/1998 e às normas do COAF, a CONTRATADA poderá comunicar às autoridades competentes quaisquer operações ou situações suspeitas identificadas no curso da prestação dos serviços, independentemente de notificação prévia ao CONTRATANTE.",
            "5.4. O CONTRATANTE autoriza expressamente a CONTRATADA a realizar consultas cadastrais, verificação de antecedentes e análise de restrições junto a bureaus de crédito, cadastros públicos e bases de dados disponíveis, incluindo Serasa, SPC, Receita Federal e BACEN, inclusive em relação aos seus sócios e representantes, para fins de validação das informações prestadas.",
            "5.5. A CONTRATADA não se responsabiliza, em hipótese alguma, por danos, perdas ou prejuízos decorrentes de informações falsas ou incompletas prestadas pelo CONTRATANTE, respondendo este civil e criminalmente por tais condutas.",
            "5.6. A CONTRATADA não mantém qualquer vínculo empregatício, societário ou de representação com as instituições financeiras parceiras, atuando de forma independente e em defesa dos interesses do CONTRATANTE, sem receber qualquer remuneração das referidas instituições em virtude deste contrato.",
            "5.7. Em caso de suspeita de uso de conta laranja, falsidade ideológica, uso de documentos de terceiros ou qualquer outra irregularidade, a CONTRATADA fica autorizada a comunicar imediatamente os fatos à Polícia Federal, ao Ministério Público e ao COAF, respondendo o CONTRATANTE por todos os danos causados à CONTRATADA, inclusive danos morais e à reputação.",
        ]),
        ("CLÁUSULA SEXTA – OBRIGAÇÕES DA CONTRATADA", [
            "6.1. São obrigações da CONTRATADA: (a) realizar análise técnica e criteriosa do perfil financeiro do CONTRATANTE; (b) orientar o CONTRATANTE sobre a documentação necessária; (c) intermediar o relacionamento com instituições financeiras parceiras; (d) manter sigilo sobre as informações do CONTRATANTE; (e) comunicar o andamento do processo de crédito; (f) agir com diligência, ética e boa-fé em todas as etapas.",
        ]),
        ("CLÁUSULA SÉTIMA – OBRIGAÇÕES DO CONTRATANTE", [
            "7.1. São obrigações do CONTRATANTE: (a) fornecer todos os documentos, informações e dados solicitados de forma completa, verdadeira e tempestiva; (b) informar imediatamente a CONTRATADA sobre qualquer contato direto recebido de instituições financeiras relacionado ao processo de intermediação ora contratado; (c) não contratar a modalidade de crédito intermediada pela CONTRATADA de forma direta ou por terceiros durante a vigência deste contrato e pelos 12 (doze) meses subsequentes ao encerramento, sob pena de ser considerado êxito da CONTRATADA, com cobrança integral dos honorários previstos; (d) efetuar o pagamento dos honorários de êxito exclusivamente pela forma de pagamento informada pela CONTRATADA, no prazo e forma estabelecidos; (e) não prestar informações falsas nem documentos adulterados, sob pena de rescisão imediata e responsabilidade civil e criminal.",
            "7.2. A violação da obrigação prevista no item 7.1.c sujeitará o CONTRATANTE, além do pagamento integral dos honorários de êxito calculados sobre o valor do crédito contratado, ao pagamento de multa compensatória equivalente a 30% (trinta por cento) do valor do crédito obtido, a título de perdas e danos prefixados, sem prejuízo de indenização suplementar caso os prejuízos efetivos superem o valor da multa.",
        ]),
        ("CLÁUSULA OITAVA – PRAZO E VIGÊNCIA", [
            "8.1. O presente contrato entra em vigor na data de sua assinatura e vigorará pelo prazo de 12 (doze) meses, podendo ser prorrogado por igual período mediante acordo expresso entre as partes.",
            "8.2. A obrigação de pagamento dos honorários de êxito persiste mesmo após o encerramento do contrato, caso o crédito seja liberado em decorrência de gestões iniciadas durante sua vigência, pelo prazo adicional de 12 (doze) meses.",
            "8.3. A rescisão antecipada por parte do CONTRATANTE não o exime do pagamento de honorários sobre créditos que venham a ser liberados em razão de processos já iniciados pela CONTRATADA.",
        ]),
        ("CLÁUSULA NONA – RESCISÃO CONTRATUAL", [
            "9.1. O contrato poderá ser rescindido por qualquer das partes mediante notificação escrita com antecedência mínima de 30 (trinta) dias, sem prejuízo das obrigações já constituídas.",
            "9.2. A CONTRATADA poderá rescindir imediatamente e sem qualquer ônus nas seguintes hipóteses: (i) fornecimento de documentos ou informações falsas; (ii) suspeita fundamentada de irregularidades financeiras ou uso de laranja; (iii) inadimplemento contratual; (iv) conduta que comprometa a relação de confiança ou exponha a CONTRATADA a risco reputacional ou legal.",
            "9.3. A rescisão não extingue a Confissão de Dívida firmada na Cláusula Quarta, cujos efeitos permanecem íntegros até quitação integral.",
        ]),
        ("CLÁUSULA DÉCIMA – CONFIDENCIALIDADE", [
            "10.1. Ambas as partes obrigam-se a manter em absoluto sigilo todas as informações, dados, documentos e estratégias obtidos em virtude deste contrato, comprometendo-se a não divulgá-los a terceiros sem autorização prévia e expressa.",
            "10.2. A violação da obrigação de confidencialidade sujeitará a parte infratora ao pagamento de indenização por perdas e danos, sem prejuízo das sanções civis e penais aplicáveis.",
        ]),
        ("CLÁUSULA DÉCIMA PRIMEIRA – PROTEÇÃO DE DADOS (LGPD)", [
            "11.1. O CONTRATANTE autoriza a coleta, o armazenamento e o tratamento de seus dados pessoais e empresariais, inclusive dos seus sócios e representantes, pela CONTRATADA, exclusivamente para as finalidades previstas neste contrato, em conformidade com a Lei nº 13.709/2018 (LGPD).",
            "11.2. A CONTRATADA adotará medidas técnicas e administrativas para proteger os dados do CONTRATANTE contra acessos não autorizados, perda ou divulgação indevida.",
            "11.3. O CONTRATANTE poderá, a qualquer tempo, solicitar acesso, correção ou exclusão de seus dados pessoais, exceto quando a manutenção dos dados for necessária para: (i) cumprimento de obrigação legal ou regulatória pela CONTRATADA; (ii) exercício regular de direitos em processo judicial, administrativo ou arbitral; (iii) proteção do crédito; ou (iv) execução de contrato ou procedimentos preliminares a contrato do qual o CONTRATANTE seja parte, nos termos do art. 16 da Lei nº 13.709/2018.",
        ]),
        ("CLÁUSULA DÉCIMA SEGUNDA – LIMITAÇÃO DE RESPONSABILIDADE", [
            "12.1. A CONTRATADA não se responsabiliza pela decisão final das instituições financeiras quanto à aprovação ou reprovação do crédito solicitado.",
            "12.2. A CONTRATADA não responde por alterações nas políticas de crédito das instituições financeiras que possam impactar o processo de análise ou aprovação.",
            "12.3. A CONTRATADA não se responsabiliza por danos decorrentes de informações falsas prestadas pelo CONTRATANTE.",
        ]),
        ("CLÁUSULA DÉCIMA TERCEIRA – ANEXOS INTEGRANTES", [
            "13.1. Integra este contrato como parte indissociável o Anexo I – Registro de Créditos Liberados e Honorários Devidos, que deverá ser preenchido e assinado pelas partes a cada operação de crédito efetivamente liberada.",
            "13.2. O Anexo I, devidamente preenchido e assinado, terá o mesmo valor jurídico e executivo do contrato principal, reforçando e detalhando a Confissão de Dívida prevista na Cláusula Quarta.",
        ]),
        ("CLÁUSULA DÉCIMA QUARTA – DISPOSIÇÕES GERAIS", [
            "14.1. Este contrato representa o acordo integral entre as partes, substituindo quaisquer negociações, propostas ou acordos anteriores.",
            "14.2. Qualquer alteração somente terá validade se feita por escrito e assinada por ambas as partes.",
            "14.3. A tolerância em relação ao descumprimento de qualquer obrigação não implica renúncia ao direito de exigi-la posteriormente.",
            "14.4. Se qualquer cláusula for declarada nula, as demais permanecerão em pleno vigor.",
        ]),
        ("CLÁUSULA DÉCIMA QUINTA – DA VEDAÇÃO À CESSÃO CONTRATUAL", [
            "15.1. O CONTRATANTE não poderá ceder, transferir ou sub-rogar, total ou parcialmente, os direitos e obrigações decorrentes deste contrato a terceiros sem a prévia e expressa autorização por escrito da CONTRATADA.",
            "15.2. A CONTRATADA poderá ceder livremente seus direitos creditórios decorrentes deste contrato a terceiros, independentemente de anuência do CONTRATANTE, mediante simples notificação.",
        ]),
        ("CLÁUSULA DÉCIMA SEXTA – COMUNICAÇÕES E NOTIFICAÇÕES", [
            "16.1. Todas as comunicações e notificações entre as partes serão consideradas válidas quando realizadas por e-mail com confirmação de leitura, por aplicativo de mensagens instantâneas (WhatsApp) ou por carta registrada com aviso de recebimento, para os endereços e números indicados no preâmbulo deste contrato.",
            "16.2. A comunicação enviada aos endereços eletrônicos, números telefônicos ou endereços físicos indicados no preâmbulo será considerada recebida: (i) na data do envio, para comunicações eletrônicas e mensagens instantâneas; (ii) na data do recebimento comprovado pelo AR, para cartas registradas.",
            "16.3. A alteração dos dados de contato deverá ser comunicada por escrito à outra parte em até 05 (cinco) dias úteis, sob pena de serem consideradas válidas as comunicações enviadas ao último endereço ou número informado.",
        ]),
        ("CLÁUSULA DÉCIMA SÉTIMA – FORO", [
            "17.1. As partes elegem o Foro da Comarca de Recife, Estado de Pernambuco, como competente para dirimir quaisquer litígios decorrentes deste instrumento, com renúncia a qualquer outro, por mais privilegiado que seja.",
        ]),
    ]


NOTA_JURIDICA = ("NOTA: Este instrumento, assinado eletronicamente pelas partes, constitui título executivo extrajudicial "
                 "nos termos do art. 784, III do CPC. Pagamentos somente são válidos se realizados pela forma de pagamento "
                 "informada pela CONTRATADA.")
