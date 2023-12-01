# Exercise K - Bot syncing

My JS/TS skills still need improvement, so for greater efficiency I made the script in Python.

To avoid rate limitation or provider issues, I'm using the [Lido Finance Web3 Multi Provider](https://github.com/lidofinance/web3py-multi-http-provider), which will switch between provider on errors or network issues.
The tx nonce is managed using a queue, so we have only one tx after another.
The bot is deployed on an AWS instance, as a service, and restart on error.


The first actions of the bot are the recovery:
- check if we having pending Pong txs, if so get the matching Ping tx block and get the potential other unprocessed Ping in this block
- if not, get last pong tx and do the same process as above
- get all the Ping events since the previously found block
- then start listening after this block

We can also imagine some alerts, which trigger for example when the account balance is low in ETH.

# Install & run

```
pip install -r requirements.txt
py bot.py
```

On AWS the bot is installed as a service.
