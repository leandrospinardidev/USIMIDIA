# ERP Industrial Web (Frontend)

Status atual: **Fase inicial implementada**

Implementado nesta etapa:
- scaffold React + Vite + TypeScript + Tailwind CSS;
- tela de operacao MES com:
  - lista de OPs,
  - detalhe da OP e operacoes,
  - botoes de evento START/PAUSA/RETOMADA/STOP,
  - registro de refugo,
  - resumo de tempo/eventos/refugos em tempo real.

## Rodar local

```bash
npm install
npm run dev
```

Frontend por padrao em:
- `http://localhost:5173`

Backend esperado em:
- `http://localhost:8000/api/v1`

Se precisar alterar a URL da API, crie `.env.local`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## Scripts

- `npm run dev`
- `npm run build`
- `npm run preview`
- `npm run typecheck`

## Referencias

- `docs/processos/playbook-operacao-api-e-go-live.md`
- `docs/arquitetura/roadmap-frontend.md`

