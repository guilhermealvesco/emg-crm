# EMG CRM

Sistema interno da EMG Soluções Empresariais para gerir os captadores comissionados da consultoria de crédito.
FastAPI + PostgreSQL + Docker, com a identidade visual da EMG, pensado para uso no celular.

## O que o sistema faz (v1)

| Módulo | Como funciona |
|---|---|
| Entrada de leads | Captador registra CNPJ, contato, origem, observação e (com aceite LGPD) os CPFs dos sócios. Primeiro a registrar é dono por 90 dias, renovável a cada contato registrado. Duplicidade é arbitrada pelo sistema (dono vigente bloqueia; posse expirada em lead parado transfere). |
| Enriquecimento + pré-score | BrasilAPI / Minha Receita (gratuitos) para situação, idade, porte, CNAE, capital e QSA. APIBrasil (créditos) para protestos, negativações e débitos federais do CNPJ e dos sócios (só com aceite LGPD). Gera pré-score verde/amarelo/vermelho com os fatores exibidos. Não descarta ninguém: a triagem é humana. |
| Triagem | Guilherme/Eduarda aprovam ou reprovam. Aprovar envia para "Nos bancos" e cria as tarefas (enviar aos bancos; dar posição ao cliente). |
| Matriz de bancos | Itaú, Santander, Bradesco, Caixa e BNB por lead. Fila da Eduarda em `/bancos`, com botões de um toque (Enviado / Bom / Ruim) e formulário de valor estimado + observação. Alerta "falta enviar pra X" após 3 dias. |
| Funil com trava | Novo → Triagem → Nos bancos → Retorno → Cobrança/contrato → Docs → Liberação → Comissão paga. Contrato e tarifa só depois de um retorno BOM de algum banco. |
| Alertas e tarefas | Sem movimentação 7 dias, sem follow-up 30 dias, docs pendentes, posse vencendo. Rotina diária (07:15) cria a tarefa "dar posição ao cliente" a cada 7 dias para leads ativos. |
| Contrato | Gera o contrato padrão da EMG em PDF (consultoria para estruturação e captação de crédito, 9 cláusulas, êxito 15% até R$ 500 mil + 10% no excedente; captador edita só qualificação, tarifa e forma de pagamento), envia pelo Autentique com documento + selfie + prova de vida, e o webhook arquiva o PDF assinado e avança o lead para "Docs". Arquivo: `{Nome-da-Empresa}-Contrato-Consultoria-Credito.pdf`. Confirmação de pagamento manual. |
| Comissões e ranking | Liberação registrada calcula a comissão (tarifa: excedente acima do piso de R$ 5.000; êxito: 3%+1% indicação, 5%+2% fechamento, teto de R$ 500 mil). Comissão só é marcada como paga após a EMG receber. Ranking por volume, contratos, aprovados e leads em `/ranking`. |

Perfis: `admin` (Guilherme), `operacao` (Eduarda), `captador` (vê só os próprios leads).

## Instalação na VPS

```bash
# na VPS, como root
git clone git@github.com:SEU_USUARIO/emg-crm.git /root/emg-crm   # ou https com token
cd /root/emg-crm
bash deploy/install.sh          # 1ª vez: cria o .env e para
nano .env                       # preencha PUBLIC_URL, CRM_DOMAIN, tokens APIBrasil e Autentique
bash deploy/install.sh          # sobe Postgres + app + Caddy e cria os usuários (senhas impressas no terminal)
```

- Aponte o DNS de `CRM_DOMAIN` (ex.: `crm.emfinanceira.com`) para o IP da VPS antes de subir: o Caddy emite o HTTPS sozinho.
- Sem domínio, deixe `CRM_DOMAIN=:80` e `PUBLIC_URL=http://IP`: funciona por HTTP, mas o webhook do Autentique exige HTTPS.
- Atualizar: `bash deploy/update.sh`. Backup diário: `bash deploy/backup.sh` (agende no cron).
- Logs: `docker compose logs -f app`.

## Fornecedores

**APIBrasil**: `POST {APIBRASIL_URL}/consulta/{cnpj|cpf}/credits` com `{"tipo": ..., "cnpj": ..., "homolog": true}`.
Com `APIBRASIL_HOMOLOG=true` nada é debitado. Os tipos de consulta ficam no `.env`; ajuste conforme o catálogo
contratado (`GET https://gateway.apibrasil.io/api/v2/documentations`). O retorno bruto fica guardado no lead
(seção "Retornos brutos dos bureaus") para calibrar a leitura automática nos primeiros 30 dias.

**Autentique**: token em `AUTENTIQUE_TOKEN`; `AUTENTIQUE_SANDBOX=true` cria documentos de teste.
Cadastre o webhook no painel (Desenvolvedor → Webhooks) apontando para `https://SEU_DOMINIO/webhooks/autentique`,
eventos `document.finished`, `signature.accepted`, `signature.rejected`, e copie o secret para
`AUTENTIQUE_WEBHOOK_SECRET`. O botão "Verificar status" na página do contrato cobre qualquer falha do webhook.

## Desenvolvimento local

```bash
pip install -r requirements.txt
cp .env.example .env            # ou exporte as variáveis
python -m scripts.seed          # usa SQLite em storage/emg.db por padrão
uvicorn app.main:app --reload
pytest                          # fluxo completo com fontes externas simuladas
```

## Estrutura

```
app/
  config.py            variáveis e regras de negócio
  models.py            tabelas (users, leads, activities, bank_submissions, tasks, contracts, disbursements)
  enrichment/          cadastral.py (BrasilAPI/MinhaReceita), apibrasil.py, prescore.py, service.py
  services/            leads (posse), funnel (travas), banks, alerts, commissions, contracts, autentique, disbursements
  routers/             páginas e ações por módulo; webhooks.py recebe o Autentique
  templates/ static/   interface (Jinja2, CSS próprio com a identidade EMG, sem framework)
scripts/seed.py        cria tabelas e usuários iniciais
deploy/                install.sh, update.sh, backup.sh, Caddyfile
tests/test_flow.py     regras de comissão, posse, trava do funil, contrato e webhook
```
