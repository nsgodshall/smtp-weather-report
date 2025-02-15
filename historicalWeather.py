import requests
import pandas as pd
from dotenv import load_dotenv
import os
import datetime
from requests.adapters import HTTPAdapter, Retry
load_dotenv()

NOAA_TOKEN = os.getenv("NOAA_TOKEN")
token = NOAA_TOKEN
CA_FIPS = "06037"
headers = {"token": token}

class HistoricWeatherRetriever():
    def __init__(self, date: datetime.datetime):
        self.date = date
        self.date_str_for_url = date.strftime('%m-%d')
        self.maxTmax = None
        self.minTmax = None
        self.maxTmin = None
        self.minTmin = None
        self.maxPrcp = None
        self.averageTmax = None
        self.averageTmin = None
        self.totalDidDaysRain = None
        self.minYear = 1950
        self.maxYear = 2024

        retry_strategy = Retry(
        total=5,  # Max retries
        backoff_factor=2,  # Exponential backoff (2, 4, 8, etc.)
        status_forcelist=[500, 502, 503, 504],  # Retry on these errors
        allowed_methods=["GET"],  # Only retry GET requests
        )

        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)

    def runJob(self):
        # get high info
        totalTmax = 0
        totalTmin = 0
        self.maxTmax = (0, 1950)
        self.minTmax = (999, 1950)
        self.maxTmin = (0, 1950)
        self.minTmin = (999, 1950)
        self.maxPrcp = (0, 1950)
        self.totalDidDaysRain = 0

        for year in range(self.minYear, self.maxYear):
            url = f"https://www.ncei.noaa.gov/cdo-web/api/v2/data?datasetid=GHCND&locationid=ZIP:91505&startdate={str(year)}-{self.date_str_for_url}&enddate={str(year)}-{self.date_str_for_url}&units=standard"
            response = self.session.get(url, headers=headers, timeout=10)
            df = pd.DataFrame()
            try:
                df = df.from_records(response.json()["results"])
            except KeyError:
                print(response.text)
                continue
            tmax = float(df[df["datatype"] == "TMAX"]["value"].values[0])
            tmin = float(df[df["datatype"] == "TMIN"]["value"].values[0])
            prcp = float(df[df["datatype"] == "PRCP"]["value"].values[0])

            if prcp > 0:
                didRain = True
            else:
                didRain = False

            if tmax > self.maxTmax[0]:
                self.maxTmax = (tmax, year)    
            if tmax < self.minTmax[0]:
                self.minTmax = (tmax, year)   

            if tmin > self.maxTmin[0]:
                self.maxTmin = (tmin, year)
            if tmin < self.minTmin[0]:
                self.minTmin = (tmin, year)

            if prcp > self.maxPrcp[0]:
                self.maxPrcp = (prcp, year)


            totalTmax += tmax
            totalTmin += tmin
            if didRain:
                self.totalDidDaysRain += 1

            print(
                f"Year: {year}, tmax: {tmax}, tmin: {tmin}, totalprcp: {prcp}, maxTmax: {self.maxTmax}, totalDaysDidRain: {self.totalDidDaysRain}"
            )

        self.averageTmax = totalTmax / (self.maxYear - self.minYear)     
        self.averageTmin = totalTmin / (self.maxYear - self.minYear)     


    def printWeatherReport(self, htmlMode = True):
        if htmlMode:
            breakChar = '<p>'
        else:
            breakChar = '\n'
        print(self.averageTmax)
        message = f"Historical weather report for {self.date.strftime("%m/%d")} {breakChar}"

        message += f"===== HIGHS ====={breakChar}"
        if self.averageTmax: 
            message += f"Average high of {int(self.averageTmax)}F{breakChar}"

        if self.maxTmax: 
            message += f"Max high of {int(self.maxTmax[0])}F in {self.maxTmax[1]} {breakChar}"

        if self.minTmax: 
            message += f"Min high of {int(self.minTmax[0])}F in {self.minTmax[1]} {breakChar}"

        message += (f"===== LOWS  ===== {breakChar}")
        if self.averageTmin: 
            message += f"Average low of {int(self.averageTmin)}F {breakChar}"
        if self.maxTmin: 
            message += f"Max low of {int(self.maxTmin[0])}F in {self.maxTmin[1]} {breakChar}"
        if self.minTmin: 
            message += f"Min low of {int(self.minTmin[0])}F in {self.minTmin[1]} {breakChar}"

        message += (f"===== PRCP  ===== {breakChar}")
        if self.maxPrcp: 
            message += f"Max percipitation of {int(self.maxPrcp[0])}\" in {self.maxPrcp[1]} {breakChar}"
        if self.totalDidDaysRain:
            message += f"It has rained {self.totalDidDaysRain} times on this date ({(self.totalDidDaysRain/(self.maxYear- self.minYear))*100:.2f}%) {breakChar}"
        print(message)
        return message
