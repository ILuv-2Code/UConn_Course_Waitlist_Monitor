import json
import requests
from bs4 import BeautifulSoup

import logging
from logging.handlers import RotatingFileHandler
import os
import sys

with open(os.path.join("creds", "creds.json"), "r") as f:
    creds = json.load(f)
    course_webhook_url = creds["course_webhook_url"]
    error_webhook_url = creds["error_webhook_url"]

#Logging
os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("worker")
logger.setLevel(logging.INFO)

#Avoid duplicate handlers on restart
if logger.handlers:
    logger.handlers.clear()

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

class InfoOnlyFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO

#Activities (INFO only)
activity_handler = RotatingFileHandler(
    os.path.join("logs", "activities.txt"),
    maxBytes=5 * 1024 * 1024, #5 MB
    backupCount=3 #Number of files created after 5MB limit (20MB of text total)
)
activity_handler.setLevel(logging.INFO)
activity_handler.setFormatter(formatter)
activity_handler.addFilter(InfoOnlyFilter())

#Errors (ERROR only)
error_handler = RotatingFileHandler(
    os.path.join("logs", "errors.txt"),
    maxBytes=5 * 1024 * 1024, #5 MB
    backupCount=3 #Number of files created after 5MB limit (20MB of text total)
)

error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

logger.addHandler(activity_handler)
logger.addHandler(error_handler)

from agent import selenium_login

#Retry loop
max_retries = 2
session_data = None

for attempt in range(max_retries):
    #Load Session Data
    try:
        if session_data is None:
            need_refresh = False
            try:
                with open(os.path.join("creds", "session.json"), "r") as f:
                    session_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Session load failed ({e}). Running Selenium login.")
                need_refresh = True

            if need_refresh:
                selenium_login()
                logger.info("Session refreshed. Reloading session data.")
                with open(os.path.join("creds", "session.json"), "r") as f:
                    session_data = json.load(f)
        
        #Prepare Request
        sess = requests.Session()
        sess.headers.update(session_data["headers"])
        sess.cookies.update(session_data["cookies"])

        #Fetch Shopping Cart Page
        url = session_data["url"]
        resp = sess.get(url, allow_redirects=True)

        if resp.status_code != 200:
            logger.error(f"Failed to fetch Shopping Cart page: {resp.status_code}")
            raise RuntimeError(f"Failed to fetch Shopping Cart page: {resp.status_code}")
        else:
            logger.info(f"Fetched Shopping Cart page ({resp.status_code})")


        #Parser
        soup = BeautifulSoup(resp.text, "html.parser")

        #Error Check
        error_p = soup.find("p", class_="error")
        if error_p and "Your User ID and/or Password are invalid." in error_p.get_text(strip=True):
            logger.info("Invalid credentials detected")
            try:
                selenium_login()
                logger.info("Session refreshed. Rerunning worker.")
                #Immediately reload the fresh session data
                with open(os.path.join("creds", "session.json"), "r") as f:
                    session_data = json.load(f)
                continue
            except Exception as e:
                logger.error(f"Selenium login failed: {e}")
                raise

        courses = []

        #Each course is one PeopleSoft grid row
        rows = soup.select("tr.ps_grid-row")

        for row in rows:
            #Get all elements at once instead of 3 separate searches
            availability_elem = row.find("span", class_="ps_box-value", id=lambda x: x and 'DERIVED_SSR_FL_SSR_AVAIL_FL' in x)
            title_elem = row.find("span", class_="ps_box-value", id=lambda x: x and 'DERIVED_SSR_FL_SSR_DESCR80' in x)
            section_elem = row.find("a", class_="ps-link", id=lambda x: x and 'DERIVED_SSR_FL_SSR_CLASSNAME_LONG' in x)
            
            #Skip row if any required element is missing
            if not all([availability_elem, title_elem, section_elem]):
                continue

            courses.append({
                "course": title_elem.get_text(strip=True),
                "section": section_elem.get_text(strip=True),
                "availability": availability_elem.get_text(strip=True)
            })
            

        #Prepare Results Payload
        if not courses:
            payload = {
                "content": "No courses found — Shopping Cart grid not present"
            }
        else:
            fields = [
                {
                    "name": c["course"],
                    "value": f"Section: {c['section']}\nStatus: {c['availability']}",
                    "inline": False,
                }
                for c in courses
            ]
            
            any_open = any("Open" in c["availability"] for c in courses)

            payload = {
                "content": f"{'Courses Available!' if any_open else 'No Available Courses'}",
                "embeds": [
                    {
                        "title": "Shopping Cart Course Status",
                        "description": "Current availability from PeopleSoft",
                        "color": 0x2ecc71 if any_open else 0xe74c3c,
                        "fields": fields
                    }
                ]
            }

        #Send to Discord
        requests.post(course_webhook_url, json=payload, timeout=5)
        
        #Success --> break out of retry loop
        break   
    
    except Exception as e:
        logger.error(f"Error on attempt {attempt + 1}/{max_retries}: {e}")
        if attempt == max_retries - 1:
            requests.post(error_webhook_url, json={"content":"Max retires reached. Script Stopped. Check Logs."}, timeout=5)
            logger.error("Max retries reached. Exiting.")
            raise
        #Reset session_data so it gets reloaded on next attempt
        session_data = None

sys.exit(0)