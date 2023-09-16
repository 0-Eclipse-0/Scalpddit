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

SEARCH_QUERY_1 = "" # Item name
SEARCH_QUERY_2 = "" # Extra tag (leave blank to ignore)
LINK = ""
SLEEP_TIME = 10 # Time to wait before checking again (Seconds)
TARGET_EMAIL = ""
SENDER_EMAIL = ""
APP_PASSWORD = ""

class Scalper:
    def __init__(self, url):
        # Initialize headless browser
        chromeArgs = webdriver.ChromeOptions()
        chromeArgs.add_argument('headless')

        self.target = url
        self.driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chromeArgs)

        try:
            self.driver.get(url)
        except Exception as e:
            print(e)

    # Modify and parse source for useful information
    def getSource(self):
        # Scroll to get all posts
        for i in range(1, 10):
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);")

            # Remove price deductions


            sleep(4)

        # Javascript to remove price deductions
        self.driver.execute_script(
            """
            const deductions = document.getElementsByClassName("xmqliwb");

            for (let i = deductions.length - 1; i >= 0; i--) {
                deductions[i].parentNode.removeChild(deductions[i]);
            }
            """
        );

    # Get information from each post
    def getPosts(self):
        posts = []

        soup = BeautifulSoup(self.driver.page_source, 'lxml')

        for post in soup.findAll('shreddit-post'):
            # innerText = post.getText(separator=':').split(':')
            innerText = [post.find('div', attrs={"slot": "title"}).getText().strip(),
                         "https://reddit.com" + post.find('a', attrs={"slot": "full-post-link"})['href']]
            posts.append(innerText)

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

        self.emailPass = APP_PASSWORD  # Import
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
            content += "\n\t\t• %s" % (', '.join(i[:len(i)]))

        self.message.attach(MIMEText(content, "plain"))  # Add html compatibility # TODO
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

def startProgram(db):
    newPosts = []

    db.createTable(SEARCH_QUERY_1)

    print("\rWaiting for search to complete (Approx: 40s)", end="")

    browser = Scalper(LINK)
    browser.getSource()

    # Parse posts from sourced list
    for i in parsePosts(browser.getPosts()):
        if db.entryExists(SEARCH_QUERY_1, i[0], i[1]):  # Add to database if not found
            newPosts.append(i)
            db.insertPost(SEARCH_QUERY_1, i[0], i[1])
            db.database.commit()
    browser.end()

    return newPosts

def parsePosts(original):
    posts = []

    for post in range(len(original)):
        original[post][1].replace('\'', "").replace('\"', "") # Prevent SQL error

        if original[post][0].lower().__contains__(SEARCH_QUERY_1) and \
                original[post][0].lower().__contains__(SEARCH_QUERY_2):
            posts.append(original[post])

    return posts

if __name__ == '__main__':
    db = Database()
    notification = Notification(SENDER_EMAIL, TARGET_EMAIL)

    print(f"""Running Scalper...
    Arguments:
    \t- Search Query 1: {SEARCH_QUERY_1 if SEARCH_QUERY_1 else "N/A"}
    \t- Search Query 2: {SEARCH_QUERY_2 if SEARCH_QUERY_2 else "N/A"}
    \t- Link: {LINK}
    \t- Target Email: {TARGET_EMAIL}
    \t- Sender Email: {SENDER_EMAIL}
          """)

    try:
        while True:
            posts = startProgram(db)

            # Output newly found posts
            if posts == []:
                print("\rNo new posts found!")
            else:
                print("\rAll new posts:")


                for i in posts:
                    print("\t\t• " + ", ".join(i))

                # Send email
                notification.email(posts)

            # Wait Timer
            i = 0
            while i != SLEEP_TIME:
                print("\rChecking again in %.2f minutes..." % ((SLEEP_TIME - i) / 60), end="")
                sleep(1)
                i += 1

    except KeyboardInterrupt:
        print("Exiting...")
        db.database.close()

