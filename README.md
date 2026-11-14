# ai-support-agent

**An AI customer support agent for online stores that answers order, shipping, returns and product questions from your real store data, and hands anything it shouldn't decide to a human.**

> **Status:** early development. Not ready for production use yet.

## What it does

- **Answers "Where's my order?"** by looking up the real order status, after checking that the customer owns the order.
- **Answers policy and product questions** (shipping, returns, sizing, materials) from your own policies and catalog, and shows the sources it used.
- **Hands off to a human** for refunds, complaints and anything it isn't sure about, with a summary so your team doesn't have to re-read the chat.
- **Embeds in any website** with one `<script>` tag.
- **Admin page** showing conversations, handoffs and questions it couldn't answer.

## Design principles

- **Safe by default.** The agent can read store data. Anything that changes money or orders goes to a person.
- **Grounded answers.** Policy answers come from your documents, with sources. If the answer isn't there, it says so instead of guessing.
- **Works without paid services.** A built-in demo store and local embeddings mean `docker compose up` runs the full demo. Connect Shopify and your preferred LLM when you're ready.

## License

[MIT](LICENSE)
