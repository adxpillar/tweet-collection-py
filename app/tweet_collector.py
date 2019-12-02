import os
from pprint import pprint

from dotenv import load_dotenv
import tweepy
from tweepy.streaming import StreamListener
from tweepy import OAuthHandler
from tweepy import Stream

from app import APP_ENV
from app.storage_service import append_to_csv, append_to_bq #, TWEET_COLUMNS, USER_COLUMNS

load_dotenv()

CONSUMER_KEY = os.getenv("TWITTER_CONSUMER_KEY", default="OOPS")
CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET", default="OOPS")
ACCESS_KEY = os.getenv("TWITTER_ACCESS_TOKEN", default="OOPS")
ACCESS_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", default="OOPS")

TOPICS_LIST = ["impeach"] # todo: dynamically compile list from comma-separated env var string like "topic1,topic2"
#TOPICS_LIST = ["impeach -filter:retweets"] # doesn't work

def is_collectable(status):
    return (status.lang == "en"
            #and status.user.verified
            and status.in_reply_to_status_id == None
            and status.in_reply_to_user_id == None
            and status.in_reply_to_screen_name == None
            and status.is_quote_status == False
            and status.retweeted == False
            #and status.retweeted_status == None #> AttributeError: 'Status' object has no attribute 'retweeted_status'
            and not hasattr(status, "retweeted_status")
    )

def parse_full_text(status):
    # GET FULL TEXT (THIS SHOULD BE EASIER)
    # h/t: https://github.com/tweepy/tweepy/issues/974#issuecomment-383846209

    #if hasattr(status, "retweeted_status"):
    #    try:
    #        full_text = status.retweeted_status.extended_tweet["full_text"]
    #    except:
    #        full_text = status.retweeted_status.text
    #else:
    #    try:
    #        full_text = status.extended_tweet["full_text"]
    #    except AttributeError:
    #        full_text = status.text

    if hasattr(status, "retweeted_status"):
        sts = status.retweeted_status
    else:
        sts = status

    if hasattr(sts, "full_text"):
        full_text = sts.full_text
    elif hasattr(sts, "extended_tweet"):
        full_text = sts.extended_tweet["full_text"]
    else:
        full_text = sts.text

    full_text = full_text.replace("\n"," ") # remove line breaks for cleaner storage
    #print(status.id_str, status.user.screen_name.upper(), "says:", full_text)

    return full_text

def parse_status(status):
    full_text = parse_full_text(status)
    twt = status._json
    usr = twt["user"]

    tweet = {
        "id_str": twt["id_str"],
        "full_text": full_text, #> 'Refuse censure! Make them try to impeach and beat it. Mr President you are guilty of no crime. Continue the exposure of these subversives that are so desperate to smear you for draining the swamp!'
        "geo": twt["geo"], #> None or __________
        "created_at": twt["created_at"], #> 'Mon Dec 02 01:06:52 +0000 2019'
        #"timestamp_ms": twt["timestamp_ms"], Not in all tweets WAT?
        "user_id_str": usr["id_str"],
        "user_screen_name": usr["screen_name"],
        "user_description": usr["description"].replace("\n"," "), # remove line breaks for cleaner storage
        "user_location": usr["location"],
        "user_verified": usr["verified"],
    }

    return tweet

class TweetCollector(StreamListener):

    def __init__(self):
        self.auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
        self.auth.set_access_token(ACCESS_KEY, ACCESS_SECRET)
        self.api = tweepy.API(self.auth)
        self.counter = 0
        self.max = 25 # TODO: config via env var

    def on_status(self, status):
        if is_collectable(status):
            self.counter +=1
            print("----------------")
            print(f"DETECTED AN INCOMING TWEET! ({self.counter})")
            tweet = parse_status(status)
            pprint(tweet)
            if APP_ENV == "development":
                append_to_csv(tweet)
            elif APP_ENV == "production":
                append_to_bq(tweet)

    def on_connect(self):
        print("LISTENER IS CONNECTED!")

    def on_exception(self, exception):
        print("EXCEPTION:", type(exception))
        print(exception)

    def on_error(self, status_code):
        print("ERROR:", status_code)

    def on_limit(self, track):
        print("RATE LIMITING", type(track))
        print(track)

    def on_timeout(self):
        print("TIMEOUT!")
        #print("STAYING ALIVE...")
        #return True # don't kill the stream! TODO: implement back-off

    def on_warning(self, notice):
        print("DISCONNECTION WARNING:", type(notice))
        print(notice)

    def on_disconnect(self, notice):
        print("DISCONNECT:", type(notice))
        print(notice)

if __name__ == "__main__":

    print("COLLECTING TWEETS IN", APP_ENV.upper())

    listener = TweetCollector()
    print("LISTENER", type(listener))

    stream = Stream(listener.auth, listener)
    print("STREAM", type(stream))

    print("TOPICS:", TOPICS_LIST)
    stream.filter(track=TOPICS_LIST) #TODO: track=listener.topics_list

    # this never gets reached
