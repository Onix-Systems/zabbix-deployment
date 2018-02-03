#!/usr/bin/python

import os
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.keys import Keys

selenium_url = "http://{:s}:{:s}/wd/hub".format(os.environ["SELENIUM_ADDRESS"],os.environ["SELENIUM_PORT"])

driver = webdriver.Remote(
   command_executor=selenium_url,
   desired_capabilities=DesiredCapabilities.CHROME)

driver.get("http://{:s}".format(os.environ["ZBX_SERVER_NAME"]))
title_prefix = os.environ["ZBX_SERVER_NAME"] + ":"
print "Checking window title -",
try:
    assert "{:s} Zabbix".format(title_prefix) == driver.title
    print "SUCCESS."
except:
    print "FAILED."

print "Login into Zabbix UI -",
try:
    loginField = driver.find_element_by_name("name")
    loginField.send_keys("admin")
    passwordField = driver.find_element_by_name("password")
    passwordField.send_keys(os.environ["ZBX_ADMIN_PASSWORD"])
    passwordField.send_keys(Keys.RETURN)
    assert "{:s} Dashboard".format(title_prefix) == driver.title
    print "SUCCESS."
    print "Logout from Zabbix UI -",
    try:
        inputElement = driver.find_elements_by_class_name("top-nav-signout")
        inputElement[0].click()
        print "SUCCESS."
    except:
        print "FAILED."
except:
    print "FAILED ({:s}).".format(driver.title)

driver.quit()
