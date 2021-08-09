rough instructions to get started:

1. add a `.env` file to `./src/adonis_blue/` containing the following:
```
OPENAI_API_KEY=<your-api-key>
DISCORD_API_KEY=<your-bot-api-key>
GUILD_IDS=[<guild-id-where-your-bot-will-listen-for-slash-commands>,...]
```
2. `docker-compose build && docker-compose up -d adonis_blue`
