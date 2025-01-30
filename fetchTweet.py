import snscrape.modules.twitter as sntwitter
import pandas as pd
import json

# Twitter username to scrape
USERNAME = "team3dstocks"
TWEETS_LIMIT = 10000  # Adjust the limit as needed

# List to store tweet data
tweets_data = []

# Scrape tweets
for i, tweet in enumerate(sntwitter.TwitterUserScraper(USERNAME).get_items()):
    if i >= TWEETS_LIMIT:
        break
    tweets_data.append({
        "id": tweet.id,
        "date": tweet.date.isoformat(),
        "content": tweet.content,
        "likes": tweet.likeCount,
        "retweets": tweet.retweetCount,
        "replies": tweet.replyCount,
        "url": f"https://x.com/{USERNAME}/status/{tweet.id}"
    })

# Save as JSON for LLM analysis
with open(f"{USERNAME}_tweets.json", "w", encoding="utf-8") as f:
    json.dump(tweets_data, f, indent=4)

print(f"Saved {len(tweets_data)} tweets to {USERNAME}_tweets.json")
