# Clara FIIs 📈

**Aplicativo web responsivo** para acompanhar fundos imobiliários brasileiros, comparar indicadores, consultar notícias e simular rendimentos.

**Acessar:** https://carvalho832-glitch.github.io/clara-fiis/

## O que já funciona

- **Radar semanal** com 12 FIIs de diferentes segmentos, dados pontuados, posição na triagem, breve leitura automática do que precisa ser investigado (dívidas, vacância, informes antigos, temas de manchetes) e link para a fonte. Três nomes aparecem como candidatos para estudo, nunca como ordem de compra.
- **Notícias dos FIIs** e manchetes econômicas com data, veículo e link original.
- **Vacância física** com data de referência, quando a fonte disponibiliza esse indicador. A ausência é explicitamente sinalizada.
- **Simulador em três modos**: último rendimento por cota divulgado com fonte e data, cenário manual em R$/cota, ou cenário aproximado com percentual de informe (sem tratar esse cenário como pagamento anunciado). Mostra cotas inteiras, saldo e valor investido.
- **Agenda de proventos e data-com**: mostra o último pregão para comprar e receber o rendimento anunciado, a data-ex (se divulgada), o dia de pagamento, valor por cota e link da fonte. Inclui verificador interativo para conferir se uma compra em determinada data participa de um evento específico. Datas antigas não são usadas para prometer prazos futuros.
- **Atualização automática** de cotações, notícias e comunicados integrados **de segunda a sexta às 08h15 (horário de Brasília)** via GitHub Actions, além de execução manual. O radar continua voltado a análises semanais; os eventos dependem de fontes que possam demorar a publicar.
- **Uso no celular**, pelo navegador, com possibilidade de adicionar à tela inicial.

## Fontes

1. [Capital Agora](https://capitalagora.com.br/api): cotação de fechamento da B3, dados de informe mensal, P/VP, renda percentual e manchetes.
2. [CVM](https://dados.cvm.gov.br/dataset/fii-doc-inf_mensal): origem dos informes periódicos. A data de referência pode ser anterior à cotação.
3. [brapi](https://brapi.dev/docs/fiis): proventos exatos por cota, data-com, pagamentos e vacância. Sem token, a API pública permite demonstração com HGLG11 e MXRF11. Dados completos de todos os FIIs requerem plano **Pro** da brapi.
4. [data/proventos-verificados.json](data/proventos-verificados.json): anúncios específicos de outubro de 2026 revisados com referência jornalística e identificados como conferência manual. Os eventos deixam de ser exibidos após 65 dias, se não houver notícia posterior. Eles **não** são uma integração automática para todos os fundos.

**Precisão:** quando a fonte fornece só o rendimento percentual do informe, e não o valor anunciado por cota, a calculadora usa preço x percentual / 100 como uma **simulação**. Isso não é anúncio de dividendo, nem promessa de pagamento.

**Datas não são inventadas.** O último prazo para compra é a **data-com**, que deve estar oficialmente anunciada; depois dela, novas compras não recebem aquele pagamento. A **data-ex** só é mostrada com data específica quando a fonte a fornece. Sem anúncio futuro, aparece **A confirmar**, ainda que o último pagamento tenha sido mensal. Taxas de vacância apenas aparecem com dados estruturados; não são aplicadas como se fossem equivalentes em FIIs de recebíveis.

## Critérios automáticos de triagem

- P/VP: peso 35.
- Rendimento mensal do informe: peso 25.
- Número de cotistas: peso 10.
- Patrimônio: peso 10.
- Vacância física: peso 20, apenas quando for aplicável e estiver disponível.

Campos ausentes não recebem valores inventados. Informe muito antigo reduz a pontuação. A pontuação **não** substitui análise de crédito, concentração, dívida, emissões, contratos de aluguel e notícias recentes. O painel lê manchetes e indicadores estruturados, **não os relatórios gerenciais completos**, e por isso a classificação é apenas uma triagem. O sistema apresenta riscos e fontes para revisão antes de cada compra.

## Ativar proventos e vacância de todos os fundos (opcional)

Pode exigir assinatura paga na brapi. Confirme o plano antes de contratar.

1. Obtenha sua chave da brapi: https://brapi.dev/
2. Abra o repositório no GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
3. Crie o secret **BRAPI_TOKEN** com sua chave.
4. Vá para **Actions → Atualizar radar e publicar aplicativo → Run workflow**.

Nunca publique a chave no código, arquivo de dados, navegador ou README.

## Rodar localmente

Exige Python 3.12 ou superior e internet:

1. Execute: python scripts/update.py
2. Execute: python -m http.server 8000
3. Abra: http://localhost:8000

O coletor usa biblioteca padrão do Python. A interface usa HTML, CSS e JavaScript sem instalação de pacotes.

## Limitações e segurança

- Mercado e relatórios têm atrasos diferentes: confira sempre suas datas.
- As notícias são manchetes e links, não resumos inventados nem análises de IA.
- Datas futuras só aparecem quando anunciadas e documentadas na fonte integrada.
- Sem disponibilidade do provedor, o campo mostra indisponível. Não se reutilizam cotações velhas como atuais.
- Nenhuma compra automática. Não solicita senha de corretora.
- Sem reserva de emergência, vender ativos durante uma queda pode causar perdas.

Projeto educativo/informativo. **Não é consultoria regulamentada, recomendação individual ou garantia de rentabilidade.**

## Próxima data de compra para direito ao rendimento

Na aba **Pagamentos** há uma área de **datas-com futuras confirmadas** e outra listando os FIIs que aguardam anúncio. O usuário pode escolher um FII e simular a data em que pretende comprar. O app confronta a data escolhida com o último pregão com direito ao evento, desde que o anúncio exista na base integrada.

- Comprar até o fechamento do pregão da data-com e terminar o dia cotista em geral dá direito ao provento anunciado. Comprar na data-ex ou depois, não.
- O valor anunciado não equivale a ganho automático: a cotação pode se ajustar na data-ex, e FIIs apresentam risco de perda de capital.
- Em datas sem pregão, a compra só acontece quando houver negociação; o app sinaliza fins de semana e recomenda consultar o calendário de pregões da B3.
- Sem comunicado verificado, não aparece uma "próxima data-com" fictícia calculada com o histórico. A lista **Aguardando anúncio** mostra apenas a data-com anterior conhecida.
- Como a **brapi Pro é opcional**, a cobertura de novos anúncios para todos os 12 FIIs pode permanecer parcial. O agendamento diário não corrige ausência de cobertura de fonte; cada item usa a data e o link da fonte.

Referência educacional: https://borainvestir.b3.com.br/glossario/data-ex/
