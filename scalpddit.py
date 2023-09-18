from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from time import sleep
import smtplib, ssl
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sqlite3
from unidecode import unidecode

CONTENT_QUERY = "millesime imperial" # Content query
TITLE_QUERY = "[wts]" # title query (leave blank to ignore)
LINK = "https://www.reddit.com/r/fragranceswap/new/"
SLEEP_TIME = 1200 # Time to wait before checking again (Seconds)
TARGET_EMAIL = "matthew.hambrecht@icloud.com"
SENDER_EMAIL = "scalpnotifier@gmail.com"
APP_PASSWORD = "acnkxzvjoqaqjoxl"

class Scalper:
    def __init__(self, url):
        # Initialize headless browser
        chromeArgs = webdriver.ChromeOptions()
        chromeArgs.add_argument('no-sandbox')
        chromeArgs.add_argument('headless')

        self.target = url
        self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chromeArgs)
        self.posts = []

        try:
            self.driver.get(url)
        except Exception as e:
            print("Error connecting to site.. Are you offline?")

    # Modify and parse source for useful information
    def getSource(self):
        # Scroll to get all posts
        for i in range(1, 5):
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);")

            sleep(4)

    # Get information from each post
    def getPosts(self):
        soup = BeautifulSoup(self.driver.page_source, 'lxml')

        for post in soup.findAll('shreddit-post'):
            # innerText = post.getText(separator=':').split(':')
            innerText = [unidecode(post.find('div', attrs={"slot": "title"}).getText().strip()),
                         "https://reddit.com" + post.find('a', attrs={"slot": "full-post-link"})['href'],
                         unidecode(post.find('div', attrs={"slot": "text-body"}).getText())]
            self.posts.append(innerText)

        return self.posts

    # Retrieve only posts fitting criteria
    def parsePosts(self, original):
        posts = []

        for post in range(len(original)):
            original[post][0].replace('\'', "").replace('\"', "")  # Prevent SQL error
            original[post][2].replace('\'', "").replace('\"', "")

            # Verify post contains queries
            if original[post][0].lower().__contains__(TITLE_QUERY) and \
                    original[post][2].lower().__contains__(CONTENT_QUERY):
                posts.append(original[post])

        return posts

    # Close browser
    def end(self):
        self.driver.quit()

class Notification():
    def __init__(self, senderAddress, targetAddress):
        # Obtain email information
        self.message = MIMEMultipart("alternative")
        self.message["Subject"] = time.strftime("Scalpddit: New posts found!")
        self.message["From"] = senderAddress
        self.message["To"] = targetAddress

        self.emailPass = APP_PASSWORD
        self.senderAddress = senderAddress
        self.targetAddress = targetAddress

    def send(self):
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(self.senderAddress, self.emailPass)
            server.sendmail(
                self.senderAddress, self.targetAddress, self.message.as_string()
            )

    def email(self, posts):
        # Construct message
        content = "Post(s) Found:"

        for i in posts:
            content += "\n\t\t• " + i[0] + ", " + i[1]

        self.message.attach(MIMEText(content, "plain"))
        self.send()

class Database:
    def __init__(self):
        self.database = sqlite3.connect("posts.db", check_same_thread=False)
        self.cursor = self.database.cursor()

    def insertPost(self, post, title, link): # Insert post int db after validation
        insertString = "INSERT INTO " + ''.join(post.split()) + " (title, link) VALUES (?, ?)"

        self.cursor.execute(insertString, (title, link))

    def createTable(self, post): # Create post table if it doesn't exist
        tableString = "CREATE TABLE IF NOT EXISTS " +  ''.join(post.split()) + " (title TEXT, link TEXT);"

        self.cursor.execute(tableString)

    def readDb(self): # Output DB (debugging)
        rows = self.cursor.fetchall()

        for row in rows:
            print(row)

    def entryExists(self, post, title, link): # Output if entry already exists
        locateString = "SELECT title, link FROM " + ''.join(post.split()) + " WHERE title = ? AND link = ?"

        self.cursor.execute(locateString, (title, link))
        fetchResult = self.cursor.fetchall()

        return len(fetchResult) == 0  # true if not found

if __name__ == '__main__':
    db = Database()
    notification = Notification(SENDER_EMAIL, TARGET_EMAIL)

    print(f"""Running Scalper...
    Arguments:
    \t- Title Query: {TITLE_QUERY if TITLE_QUERY else "N/A"}
    \t- Content Query: {CONTENT_QUERY if CONTENT_QUERY else "N/A"}
    \t- Link: {LINK}
    \t- Target Email: {TARGET_EMAIL}
    \t- Sender Email: {SENDER_EMAIL}
          """)

    try:
        while True:
            newPosts = []

            db.createTable(TITLE_QUERY)

            print("\rWaiting for search to complete (Approx: 40s)", end="")

            browser = Scalper(LINK)
            browser.getSource()

            # Parse posts from sourced list
            for i in browser.parsePosts(browser.getPosts()):
                if db.entryExists(TITLE_QUERY, i[0], i[1]):  # Add to database if not found
                    newPosts.append(i)
                    db.insertPost(TITLE_QUERY, i[0], i[1])
                    db.database.commit()
            browser.end()

            # Output newly found posts
            if newPosts == []:
                print("\rNo new posts found!\t\t\t")
            else:
                print("\rAll new posts:\t\t\t")


                for i in newPosts:
                    print("\t\t• " + i[0] + ", " + i[1])

                # Send email
                notification.email(newPosts)
                print()

            # Wait Timer
            i = 0
            while i != SLEEP_TIME:
                print("\rChecking again in %.2f minutes..." % ((SLEEP_TIME - i) / 60), end="")
                sleep(1)
                i += 1

    except KeyboardInterrupt:
        print("Exiting...")
        db.database.close()

