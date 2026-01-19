from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import tempfile
import shutil

import os
import logging
logger = logging.getLogger("worker")

import requests


#funtion to call
def selenium_login():
    try:
        logger.info("Started Selenium login")

    #Creds
        with open(os.path.join("creds", "creds.json"), "r") as f:
            creds = json.load(f)
            username = creds['username']
            password = creds['password']
            duo_webhook_url = creds['duo_webhook_url']

    #Options
        profile_dir = tempfile.mkdtemp()
        options = Options()

        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-cache")
        options.add_argument("--disk-cache-size=0")
        options.add_argument("--headless=new") ###Adjust to see what's happening###
        options.add_argument("--blink-settings=imagesEnabled=false")


    #Driver
        driver = webdriver.Edge(options=options)

    #CAS Login
        try: 
            driver.get("https://login.uconn.edu/cas/login?service=https://student.studentadmin.uconn.edu:443/psp/CSPR/?cmd=start")
            driver.find_element("id", "username").send_keys(username)
            driver.find_element("id", "password").send_keys(password)
            driver.find_element("id", "submitBtn").click()
        except Exception as e:
            logger.error(f"Error during CAS login: {e}")
            raise

    #DUO Login
        try:
            number = WebDriverWait(driver, 30).until(
                lambda d: d.find_element(By.CLASS_NAME, "verification-code")
            ).text
            
            data = {
                "content": number
            }
            try:
                requests.post(duo_webhook_url, json=data)
            except Exception as e:
                logger.error(f"Exception occurred while sending Discord alert: {e}")
                raise

            duo_elem = WebDriverWait(driver, 30).until(
                lambda d: d.find_element(By.ID, "dont-trust-browser-button")
            )
            duo_elem.click()
        except Exception as e:
            logger.error(f"Error during DUO login: {e}")
            raise
            
    #Student Admin
        try:
            WebDriverWait(driver, 10).until(
                lambda d: d.title == "Homepage"
            )

            student_elem = WebDriverWait(driver, 10).until(
                lambda d: d.find_element(By.ID, "win0divPTNUI_LAND_REC_GROUPLET$7")
            )

            driver.execute_script("arguments[0].scrollIntoView(true);", student_elem)

            driver.execute_script("arguments[0].click();", student_elem)
        except Exception as e:
            logger.error(f"Error navigating to Student Admin: {e}")
            raise

    #Shopping Cart
        try:
            shopping_cart_div = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//div[@steplabel='Shopping Cart']"))
            )
            
            shopping_cart_url = shopping_cart_div.get_attribute("href")
            driver.get(shopping_cart_url)
        except Exception as e:
            logger.error(f"Error navigating to Shopping Cart: {e}")
            raise

    #Grab Data

        try:
        #Cookies
            cookies = {c['name']: c['value'] for c in driver.get_cookies() if c['name']}

        #Current URL
            current_url = driver.current_url

        #State tokens
            state_tokens = {}
            hidden_inputs = driver.find_elements(By.XPATH, "//input[@type='hidden']")
            for inp in hidden_inputs:
                name = inp.get_attribute("name")
                value = inp.get_attribute("value")
                if name and value:
                    state_tokens[name] = value

        #Headers for requests
            headers = {
                "User-Agent": driver.execute_script("return navigator.userAgent;"),
                "Referer": current_url,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }

        #Persist essential session data
            session_data = {
                "url": current_url,      
                "method": "GET",         
                "cookies": cookies,      
                "headers": headers,       
                "state_tokens": state_tokens, 
            }
        except Exception as e:
            logger.error(f"Error gathering session data: {e}")
            raise

    #Save Session Data
        try:
            with open(os.path.join("creds", "session.json"), "w") as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving session data: {e}")
            raise
    except Exception as e:
        logger.error(f"Selenium login failed due to an unexpected error: {e}")
        raise
    finally:
        driver.quit()
        shutil.rmtree(profile_dir, ignore_errors=True) #Deletes temp file
        logger.info("Selenium login completed and session data saved.")