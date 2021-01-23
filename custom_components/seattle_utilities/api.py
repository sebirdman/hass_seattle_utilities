import requests
from html.parser import HTMLParser
from urllib.parse import urlencode
import json
import base64
from datetime import datetime, timedelta
import aiohttp
import async_timeout
import asyncio

accept_html = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
TIMEOUT = 10


class MyHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.dict = {}

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            for attr in attrs:
                if attr[0] == "action":
                    self.url = attr[1]

        if tag == "input":
            for attr in attrs:
                if "name" in attr:
                    self.name = attr[1]
                if "value" in attr:
                    self.value = attr[1]

    def handle_endtag(self, tag):
        if tag != "input":
            return

        self.dict[self.name] = self.value

        self.name = None
        self.value = None

    def get_form_data(self):
        return self.dict

    def get_form_url(self):
        return self.url


class SeattleUtilities:
    def __init__(self, username, password, session: aiohttp.ClientSession):
        self.username = username
        self.password = password
        self._session = session
        self.latest_data = {}

    async def __get_oracle_location(self):
        headers = {"Accept": accept_html, "Host": "myutilities.seattle.gov"}
        data = await self.api_wrapper("get", "https://myutilities.seattle.gov/rest/auth/ssologin",
                            headers=headers, allow_redirects=False)
        return data.headers["Location"]

    async def __get_oracle_cookie(self, url, cookie=None):
        if cookie == None:
          headers = {"Accept": accept_html}
        else:
          headers = {"Accept": accept_html, "Cookie": cookie}
        data = await self.api_wrapper("get", url, headers=headers, allow_redirects=False)
        text = await data.text()
        if "Location" in data.headers:
            response = {
                "cookie": data.headers["Set-Cookie"],
                "url": data.headers["Location"],
                "html": text,
            }
        else:
            response = {
                "cookie": data.headers["Set-Cookie"],
                "html": text,
            }
        return response

    async def __submit_form(self, url, data, cookie=None):
        if cookie == None:
          headers = None
        else:
          headers = {"Cookie": cookie}
        return await self.api_wrapper("post_form", url, data=data,
                             headers=headers, allow_redirects=False)

    def get_data_from_js(self, data):
        startIDX = data.find("setItem")
        idx1 = data.find("(", startIDX) + 1
        idx2 = data.find(")", idx1)

        startIDX = data.find("setItem", idx1)
        idx1 = data.find("(", startIDX) + 1
        idx2 = data.find(")", idx1)

        signinAt = data[idx1:idx2].split(
            ",")[1].replace(' ', '').replace('"', '')

        startIDX = data.find("setItem", idx1)
        idx1 = data.find("(", startIDX) + 1
        idx2 = data.find(")", idx1)

        baseUri = data[idx1:idx2].split(
            ",")[1][1:-1].replace(' ', '').replace('"', '')

        startIDX = data.find("setItem", idx1)
        idx1 = data.find("(", startIDX) + 1
        idx2 = data.find(")", idx1)

        clientId = data[idx1:idx2].split(
            ",")[1][1:-1].replace(' ', '').replace('"', '')

        startIDX = data.find("setItem", idx1)
        idx1 = data.find("(", startIDX) + 1
        idx2 = data.find(")", idx1)

        initialState = data[idx1:idx2].split(
            ",")[1][1:-1].replace(' ', '').replace('"', '')

        startIDX = data.find("setItem", idx1)
        idx1 = data.find("(", startIDX) + 1
        idx2 = data.find(")", idx1)

        commaIDX = data[idx1:idx2].find(",")

        initialState = data[idx1:idx2][commaIDX+1:]

        return {
            "signinAT": signinAt,
            "baseUri": baseUri,
            "initialState": json.loads(initialState[1:-1])
        }

    async def __do_authenticate(self, jsdata):
        json = {
            "credentials": {
                "password": self.password,
                "username": self.username,
            },
            "signinAT": jsdata["signinAT"],
            "initialState": jsdata["initialState"]
        }
        headers = {"Content-Type": "application/json"}
        data = await self.api_wrapper("post",
            "https://login.seattle.gov/authenticate", json=json, headers=headers)
        return await data.json()

    async def __start_session(self, baseuri, authnToken, cookie):
        body = {"authnToken": authnToken}
        headers = {"Cookie": cookie}
        url = "{}/sso/v1/sdk/session".format(baseuri)
        return await self.api_wrapper("post_form",
            url, data=body, headers=headers, allow_redirects=False)

    async def __submit_form_auth(self, url, formdata):
        message = "webClientIdPassword:secret".encode("utf-8")
        base64_bytes = base64.b64encode(message)
        base64_message = base64_bytes.decode('utf-8')
        headers = {"Authorization": "Basic {}".format(base64_message)}
        return await self.api_wrapper("post_form", url, data=formdata,
                             headers=headers, allow_redirects=False)

    async def login(self):
        url = await self.__get_oracle_location()
        data = await self.__get_oracle_cookie(url)
        oracle_identity_data = await self.__get_oracle_cookie(
            data["url"], data["cookie"])

        parser = MyHTMLParser()
        parser.feed(oracle_identity_data["html"])

        data = parser.get_form_data()
        url = parser.get_form_url()

        data = await self.__submit_form(url, data)
        text = await data.text()
        jsdata = self.get_data_from_js(text)

        data = await self.__do_authenticate(jsdata)

        data = await self.__start_session(
            jsdata["baseUri"], data["authnToken"], oracle_identity_data["cookie"])

        cookie = data.headers["Set-Cookie"]

        text = await data.text()
        parser = MyHTMLParser()
        parser.feed(text)

        data = parser.get_form_data()
        url = parser.get_form_url()

        data = await self.__submit_form(url, data, cookie)
        cookie = data.headers["Set-Cookie"]

        text = await data.text()
        parser = MyHTMLParser()
        parser.feed(text)

        data = parser.get_form_data()
        url = parser.get_form_url()

        form_data = await self.__submit_form(url, data, cookie)

        data = {
            "username": form_data.headers["Location"].rsplit("/", 1)[1],
            "grant_type": "password",
            "logintype": "sso"
        }
        response = await self.__submit_form_auth(
            "https://myutilities.seattle.gov/rest/oauth/token", data)
        self.auth_info = await response.json()

    async def get_accounts(self):
        payload = {
          "customerId": self.auth_info["user"]["customerId"],
          "csrId": self.auth_info["user"]["userName"]
        }
        headers = {
          "Content-Type": "application/json",
          "Authorization": "Bearer " + self.auth_info["access_token"]
        }
        data = await self.api_wrapper("post", "https://myutilities.seattle.gov/rest/account/list", json=payload, headers=headers, allow_redirects=False)
        self.accounts = await data.json()

    async def get_account_holders(self, company_code):
      payload = {
        "customerId": self.auth_info["user"]["customerId"],
        "companyCode": company_code,
        "page": "1",
        "account": [],
        "sortColumn": "DUED",
        "sortOrder": "DESC",
      }
      headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + self.auth_info["access_token"]
      }
      data = await self.api_wrapper("post", "https://myutilities.seattle.gov/rest/account/list/some", json=payload, headers=headers, allow_redirects=False)
      return await data.json()

    async def get_bill_list(self, company_code, account):
      payload = {
        "customerId": self.auth_info["user"]["customerId"],
        "accountContext": {
          "accountNumber": account["accountNumber"],
          "personId": account["personId"],
          "companyCd": company_code,
          "serviceAddress": account["serviceAddress"],
        },
        "csrId": self.auth_info["user"]["userName"],
        "type": "Consumption",
        "currentBillDate": account["currentBillDate"],
        "period": "3",
      }
      headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + self.auth_info["access_token"]
      }
      data = await self.api_wrapper("post", "https://myutilities.seattle.gov/rest/billing/comparison", json=payload, headers=headers, allow_redirects=False)
      return await data.json()

    async def get_daily_data(self, account, service_id, start, end, meter):
      payload = {
        "customerId": self.auth_info["user"]["customerId"],
        "accountContext": {
          "accountNumber": account["accountNumber"],
          "serviceId": service_id,
        },
        "startDate": start,
        "endDate": end,
        "port": meter,
      }

      headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + self.auth_info["access_token"]
      }
      data = await self.api_wrapper("post", "https://myutilities.seattle.gov/rest/usage/month", json=payload, headers=headers, allow_redirects=False)
      return await data.json()

    async def get_latest_data(self, who):
      meters = []
      for group in self.accounts["accountGroups"]:
        if group["name"] != who:
          continue
        holders = await self.get_account_holders(group["name"])
        for account in holders["account"]:
          bill_list = await self.get_bill_list(group["name"], account)
          for bill in bill_list["billList"]:
            for meter in bill["meters"]:
              if meter not in meters:
                meters.append(meter)


      time_now = datetime.now()
      time_yesterday = time_now - timedelta(days=1)
      time_now_string = time_now.strftime("%m/%d/%Y")
      time_yesterday_string = time_yesterday.strftime("%m/%d/%Y")
      raw_charge_day = time_yesterday.strftime("%Y-%m-%d")
      for meter in meters:
        meter_data = await self.get_daily_data(account, bill["serviceId"], time_yesterday_string, time_now_string, meter)
        for day in meter_data["history"]:
          if day["chargeDateRaw"] == raw_charge_day:
            self.latest_data[meter] = day["billedConsumption"]

      return self.latest_data

    async def api_wrapper(
        self, method: str, url: str, json: dict = {}, data: dict = {}, headers: dict = {}, allow_redirects: bool = True
    ) -> dict:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(TIMEOUT, loop=asyncio.get_event_loop()):
                if method == "get":
                    return await self._session.get(url, headers=headers, allow_redirects=allow_redirects)

                elif method == "post":
                    return await self._session.post(url, headers=headers, json=json, allow_redirects=allow_redirects)

                elif method == "post_form":
                    return await self._session.post(url, headers=headers, data=data, allow_redirects=allow_redirects)

        except asyncio.TimeoutError as exception:
            _LOGGER.error(
                "Timeout error fetching information from %s - %s",
                url,
                exception,
            )

        except (KeyError, TypeError) as exception:
            _LOGGER.error(
                "Error parsing information from %s - %s",
                url,
                exception,
            )
        except (aiohttp.ClientError, socket.gaierror) as exception:
            _LOGGER.error(
                "Error fetching information from %s - %s",
                url,
                exception,
            )
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.error("Something really wrong happened! - %s", exception)
