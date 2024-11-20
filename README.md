**Why this project?**

I was looking into momentum day trading as a point of interest, and I found that the free stock scanners didnt have the information that I wanted readliy availble, 
and the scanners that had the features I wanted were very expensive subscription based. So I decided to create one! Also gave me an oportuity to work with public 
APIs and async python. Both of which were concepts I wanted to work with a little.

**Methodology**

1. Use Nasdaqdatalink to grab a list of stocks that match the area of interest (small mid or large cap, avoiding penny stocks or massive caps).
2. Put that list of stock tickers into an SQLite DB, for persistance and ease of querying.
3. Call the twelvedata API with batches of tickers, to get price and volume information, then put that into a table on the same SQLite DB.
4. Have a seperate basic flask front end that puts the 10 highest movers, and 10 highest volume into a table, with a link to the tradingview chart for that stock

The methodology above allows me to quickly identify stocks with momentum (high movers), or potential to develop momentum (high volume).

**Issues**

The main issue I had was getting the data out of the API fast enough. The library provided by 12data did not seem to be performant enough to handle multiple aysnc queries
so I swapped to useing the endpoint. After making these changes I was able to quickly hit the ratelimit on the free tier API, so swapped to a paid teir. Still substaintailly
cheaper then using a paid scanner, and provides the functionality that I need. I did have to add a rate limited to my code otherwise I would regularly hit the upper limit 
of even a paid account. 