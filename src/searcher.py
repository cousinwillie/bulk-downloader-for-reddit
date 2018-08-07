import os
import sys
import random
import socket
import webbrowser

import praw
from prawcore.exceptions import NotFound, ResponseException, Forbidden

from src.tools import GLOBAL, createLogFile, jsonFile, printToFile
from src.errors import (NoMatchingSubmissionFound, NoPrawSupport,
                        NoRedditSupoort, MultiredditNotFound,
                        InvalidSortingType, RedditLoginFailed,
                        InsufficientPermission)

print = printToFile

def beginPraw(config,user_agent = str(socket.gethostname())):
    class GetAuth:
        def __init__(self,redditInstance,port):
            self.redditInstance = redditInstance
            self.PORT = int(port)

        def recieve_connection(self):
            """Wait for and then return a connected socket..
            Opens a TCP connection on port 8080, and waits for a single client.
            """
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('localhost', self.PORT))
            server.listen(1)
            client = server.accept()[0]
            server.close()
            return client

        def send_message(self, message):
            """Send message to client and close the connection."""
            self.client.send(
                'HTTP/1.1 200 OK\r\n\r\n{}'.format(message).encode('utf-8')
            )
            self.client.close()

        def getRefreshToken(self,*scopes):
            state = str(random.randint(0, 65000))
            url = self.redditInstance.auth.url(scopes, state, 'permanent')
            print("Go to this URL and login to reddit:\n\n",url)
            webbrowser.open(url,new=2)

            self.client = self.recieve_connection()
            data = self.client.recv(1024).decode('utf-8')
            param_tokens = data.split(' ', 2)[1].split('?', 1)[1].split('&')
            params = {
                key: value for (key, value) in [token.split('=') \
                for token in param_tokens]
            }
            if state != params['state']:
                self.send_message(
                    client, 'State mismatch. Expected: {} Received: {}'
                    .format(state, params['state'])
                )
                raise RedditLoginFailed
            elif 'error' in params:
                self.send_message(client, params['error'])
                raise RedditLoginFailed
            
            refresh_token = self.redditInstance.auth.authorize(params['code'])
            self.send_message(
                "<script>" \
                "alert(\"You can go back to terminal window now.\");" \
                "</script>"
            )
            return (self.redditInstance,refresh_token)

    """Start reddit instance"""
    
    scopes = ['identity','history','read']
    port = "1337"
    arguments = {
        "client_id":GLOBAL.reddit_client_id,
        "client_secret":GLOBAL.reddit_client_secret,
        "user_agent":user_agent
    }

    if "reddit_refresh_token" in GLOBAL.config:
        arguments["refresh_token"] = GLOBAL.config["reddit_refresh_token"]
        reddit = praw.Reddit(**arguments)
        try:
            reddit.auth.scopes()
        except ResponseException:
            arguments["redirect_uri"] = "http://localhost:" + str(port)
            reddit = praw.Reddit(**arguments)
            authorizedInstance = GetAuth(reddit,port).getRefreshToken(*scopes)
            reddit = authorizedInstance[0]
            refresh_token = authorizedInstance[1]
            jsonFile(GLOBAL.configDirectory / "config.json").add({
                "reddit_refresh_token":refresh_token
            })
    else:
        arguments["redirect_uri"] = "http://localhost:" + str(port)
        reddit = praw.Reddit(**arguments)
        authorizedInstance = GetAuth(reddit,port).getRefreshToken(*scopes)
        reddit = authorizedInstance[0]
        refresh_token = authorizedInstance[1]
        jsonFile(GLOBAL.configDirectory / "config.json").add({
            "reddit_refresh_token":refresh_token
        })
    return reddit

def getPosts(args):
    """Call PRAW regarding to arguments and pass it to redditSearcher.
    Return what redditSearcher has returned.
    """

    config = GLOBAL.config
    reddit = beginPraw(config)

    if args["sort"] == "best":
        raise NoPrawSupport

    if "subreddit" in args:
        if "search" in args:
            if args["subreddit"] == "frontpage":
                args["subreddit"] = "all"

    if "user" in args:
        if args["user"] == "me":
            args["user"] = str(reddit.user.me())

    if not "search" in args:
        if args["sort"] == "top" or args["sort"] == "controversial":
            keyword_params = {
                "time_filter":args["time"],
                "limit":args["limit"]
            }
        # OTHER SORT TYPES DON'T TAKE TIME_FILTER
        else:
            keyword_params = {
                "limit":args["limit"]
            }
    else:
        keyword_params = {
                "time_filter":args["time"],
                "limit":args["limit"]
            }

    if "search" in args:
        if args["sort"] in ["hot","rising","controversial"]:
            raise InvalidSortingType("Invalid sorting type has given")

        if "subreddit" in args:
            print (
                "search for \"{search}\" in\n" \
                "subreddit: {subreddit}\nsort: {sort}\n" \
                "time: {time}\nlimit: {limit}\n".format(
                    search=args["search"],
                    limit=args["limit"],
                    sort=args["sort"],
                    subreddit=args["subreddit"],
                    time=args["time"]
                ).upper(),noPrint=True,info=True
            )            
            return redditSearcher(
                reddit.subreddit(args["subreddit"]).search(
                    args["search"],
                    limit=args["limit"],
                    sort=args["sort"],
                    time_filter=args["time"]
                )
            )

        elif "multireddit" in args:
            raise NoPrawSupport("PRAW does not support that")
        
        elif "user" in args:
            raise NoPrawSupport("PRAW does not support that")

        elif "saved" in args:
            raise NoRedditSupoort("Reddit does not support that")
    
    if args["sort"] == "relevance":
        raise InvalidSortingType("Invalid sorting type has given")

    if "saved" in args:
        print(
            "saved posts\nuser:{username}\nlimit={limit}\n".format(
                username=reddit.user.me(),
                limit=args["limit"]
            ).upper(),noPrint=True,info=True
        )
        return redditSearcher(reddit.user.me().saved(limit=args["limit"]))

    if "subreddit" in args:

        if args["subreddit"] == "frontpage":

            print (
                "subreddit: {subreddit}\nsort: {sort}\n" \
                "time: {time}\nlimit: {limit}\n".format(
                    limit=args["limit"],
                    sort=args["sort"],
                    subreddit=args["subreddit"],
                    time=args["time"]
                ).upper(),noPrint=True,info=True
            )
            return redditSearcher(
                getattr(reddit.front,args["sort"]) (**keyword_params)
            )

        else:  
            print (
                "subreddit: {subreddit}\nsort: {sort}\n" \
                "time: {time}\nlimit: {limit}\n".format(
                    limit=args["limit"],
                    sort=args["sort"],
                    subreddit=args["subreddit"],
                    time=args["time"]
                ).upper(),noPrint=True,info=True
            )
            return redditSearcher(
                getattr(
                    reddit.subreddit(args["subreddit"]),args["sort"]
                ) (**keyword_params)
            )

    elif "multireddit" in args:
        print (
            "user: {user}\n" \
            "multireddit: {multireddit}\nsort: {sort}\n" \
            "time: {time}\nlimit: {limit}\n".format(
                user=args["user"],
                limit=args["limit"],
                sort=args["sort"],
                multireddit=args["multireddit"],
                time=args["time"]
            ).upper(),noPrint=True,info=True
        )
        try:
            return redditSearcher(
                getattr(
                    reddit.multireddit(
                        args["user"], args["multireddit"]
                    ),args["sort"]
                ) (**keyword_params)
            )
        except NotFound:
            raise MultiredditNotFound("Multireddit not found")

    elif "submitted" in args:
        print (
            "submitted posts of {user}\nsort: {sort}\n" \
            "time: {time}\nlimit: {limit}\n".format(
                limit=args["limit"],
                sort=args["sort"],
                user=args["user"],
                time=args["time"]
            ).upper(),noPrint=True,info=True
        )
        return redditSearcher(
            getattr(
                reddit.redditor(args["user"]).submissions,args["sort"]
            ) (**keyword_params)
        )

    elif "upvoted" in args:
        print (
            "upvoted posts of {user}\nlimit: {limit}\n".format(
                user=args["user"],
                limit=args["limit"]
            ).upper(),noPrint=True,info=True
        )
        try:
            return redditSearcher(
                reddit.redditor(args["user"]).upvoted(limit=args["limit"])
            )
        except Forbidden:
            raise InsufficientPermission("You do not have permission to do that")

    elif "post" in args:
        print("post: {post}\n".format(post=args["post"]).upper(),noPrint=True,
              info=True)
        return redditSearcher(
            reddit.submission(url=args["post"]),SINGLE_POST=True
        )

def redditSearcher(posts,SINGLE_POST=False):
    """Check posts and decide if it can be downloaded.
    If so, create a dictionary with post details and append them to a list.
    Write all of posts to file. Return the list
    """

    subList = []
    global subCount
    subCount = 0
    global orderCount
    orderCount = 0
    global gfycatCount
    gfycatCount = 0
    global imgurCount
    imgurCount = 0
    global eromeCount
    eromeCount = 0
    global directCount
    directCount = 0
    global selfCount
    selfCount = 0

    allPosts = {}

    if not GLOBAL.arguments.continuous: print("\nGETTING POSTS")
    if GLOBAL.arguments.verbose: print("\n")
    
    if not GLOBAL.arguments.continuous: postsFile = createLogFile("POSTS")

    if SINGLE_POST:
        submission = posts
        subCount += 1 
        try:
            details = {'postId':submission.id,
                       'postTitle':submission.title,
                       'postSubmitter':str(submission.author),
                       'postType':None,
                       'postURL':submission.url,
                       'postSubreddit':submission.subreddit.display_name}
        except AttributeError:
            pass

        result = checkIfMatching(submission)

        if result is not None:
            details = result
            orderCount += 1
            if GLOBAL.arguments.verbose:
                printSubmission(submission,subCount,orderCount)
            subList.append(details)

        if not GLOBAL.arguments.continuous: postsFile.add({subCount:[details]})

    else:
        try:
            for submission in posts:
                subCount += 1

                if not GLOBAL.arguments.continuous:
                    if subCount % 100 == 0 and not GLOBAL.arguments.verbose:
                        sys.stdout.write("• ")
                        sys.stdout.flush()

                    if subCount % 1000 == 0 and not GLOBAL.arguments.verbose:
                        sys.stdout.write("\n"+" "*14)
                        sys.stdout.flush()

                try:
                    details = {'postId':submission.id,
                               'postTitle':submission.title,
                               'postSubmitter':str(submission.author),
                               'postType':None,
                               'postURL':submission.url,
                               'postSubreddit':submission.subreddit.display_name}
                except AttributeError:
                    continue

                result = checkIfMatching(submission)

                if result is not None:
                    details = result
                    orderCount += 1
                    if GLOBAL.arguments.verbose:
                        printSubmission(submission,subCount,orderCount)
                    subList.append(details)

                allPosts[subCount] = [details]
        except KeyboardInterrupt:
            if GLOBAL.arguments.continuous: raise
            print("\nKeyboardInterrupt",noPrint=True)
        
        if not GLOBAL.arguments.continuous: postsFile.add(allPosts)

    if not len(subList) == 0:
        if GLOBAL.arguments.NoDownload or GLOBAL.arguments.verbose:
            print(
                f"\n\nTotal of {len(subList)} submissions found!"
            )
            print(
                f"{gfycatCount} GFYCATs, {imgurCount} IMGURs, " \
                f"{eromeCount} EROMEs, {directCount} DIRECTs " \
                f"and {selfCount} SELF POSTS",noPrint=True
            )
        else:
            if not GLOBAL.arguments.continuous: print()
        return subList
    else:
        raise NoMatchingSubmissionFound("No matching submission was found")

def checkIfMatching(submission):
    global gfycatCount
    global imgurCount
    global eromeCount
    global directCount
    global selfCount

    try:
        details = {'postId':submission.id,
                   'postTitle':submission.title,
                   'postSubmitter':str(submission.author),
                   'postType':None,
                   'postURL':submission.url,
                   'postSubreddit':submission.subreddit.display_name}
    except AttributeError:
        return None

    if 'gfycat' in submission.domain:
        details['postType'] = 'gfycat'
        gfycatCount += 1
        return details

    elif 'imgur' in submission.domain:
        details['postType'] = 'imgur'
        imgurCount += 1
        return details

    elif 'erome' in submission.domain:
        details['postType'] = 'erome'
        eromeCount += 1
        return details

    elif isDirectLink(submission.url) is not False:
        details['postType'] = 'direct'
        details['postURL'] = isDirectLink(submission.url)
        directCount += 1
        return details

    elif submission.is_self:
        details['postType'] = 'self'
        details['postContent'] = submission.selftext
        selfCount += 1
        return details

def printSubmission(SUB,validNumber,totalNumber):
    """Print post's link, title and media link to screen"""

    print(validNumber,end=") ")
    print(totalNumber,end=" ")
    print(
        "https://www.reddit.com/"
        +"r/"
        +SUB.subreddit.display_name
        +"/comments/"
        +SUB.id
    )
    print(" "*(len(str(validNumber))
          +(len(str(totalNumber)))+3),end="")

    try:
        print(SUB.title)
    except:
        SUB.title = "unnamed"
        print("SUBMISSION NAME COULD NOT BE READ")
        pass

    print(" "*(len(str(validNumber))+(len(str(totalNumber)))+3),end="")
    print(SUB.url,end="\n\n")

def isDirectLink(URL):
    """Check if link is a direct image link.
    If so, return URL,
    if not, return False
    """

    imageTypes = ['.jpg','.png','.mp4','.webm','.gif']
    if URL[-1] == "/":
        URL = URL[:-1]

    if "i.reddituploads.com" in URL:
        return URL

    elif "v.redd.it" in URL:
        return URL+"/DASH_600_K"

    for extension in imageTypes:
        if extension in URL:
            return URL
    else:
        return False
