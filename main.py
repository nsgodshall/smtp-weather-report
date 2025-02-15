import datetime
import os
import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import requests
from bs4 import BeautifulSoup
import historicalWeather
from dotenv import load_dotenv

# loading variables from .env file
load_dotenv()

LAT = os.getenv("LAT")
LONG = os.getenv("LONG")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASS = os.getenv("SENDER_PASS")
TARGET_EMAIL = os.getenv("TARGET_EMAIL")
TZ = os.getenv("TZ")


URL = f"https://forecast.weather.gov/MapClick.php?lat={LAT}&lon={LONG}&FcstType=digitalDWML"


def requestData():
    r = requests.get(URL)
    return BeautifulSoup(r.content, "xml")


def readLocalData():
    with open("output.xml", "r") as f:
        data = f.read()
    Bs_data = BeautifulSoup(data, "xml")
    return Bs_data


def getContentsFromSet(set) -> list:
    return [tag.get_text() for tag in set]


def getValuesByTag(bsData, tagName, type):
    result_set = bsData.find(tagName, type=type).find_all("value")
    return getContentsFromSet(result_set)


def processData(bsData):
    start_times_list = getContentsFromSet(bsData.find_all("start-valid-time"))
    hourly_temp = getValuesByTag(bsData, "temperature", "hourly")
    hourly_qpf = getValuesByTag(bsData, "hourly-qpf", "floating")

    df = pd.DataFrame()
    df["start_times"] = start_times_list
    df["hourly_temp"] = hourly_temp
    df["hourly_qpf"] = hourly_qpf
    df["start_times"] = pd.to_datetime(df["start_times"])
    df = df.sort_values(by="start_times")
    return df


def getStartDateTime():
    startHour = 12
    timezone = TZ
    current_date = (
        pd.Timestamp.utcnow()
        .tz_convert("UTC")
        .tz_convert(timezone)
        .replace(hour=startHour, minute=0, second=0, microsecond=0)
    )
    return current_date


def getEndDateTime():
    return getStartDateTime() + pd.Timedelta(hours=18)


def getPlotDF(df, st, et):
    start_index = df[df["start_times"] == st].index[0]
    end_index = df[df["start_times"] == et].index[0]
    df = df[start_index:end_index].reset_index()
    df["hourly_temp"] = [float(t) for t in df["hourly_temp"] if t != ""]
    df["hourly_qpf"] = [float(t) for t in df["hourly_qpf"] if t != ""]
    return df


def plot(plotDf):
    # Convert 'start_times' to datetime and handle timezones
    plotDf["start_times"] = pd.to_datetime(plotDf["start_times"])

    # Check if already timezone-aware
    if plotDf["start_times"].dt.tz is None:
        # Localize to UTC if naive (no timezone)
        plotDf["start_times"] = plotDf["start_times"].dt.tz_localize("UTC")

    # Convert to Pacific Time
    plotDf["start_times"] = plotDf["start_times"].dt.tz_convert("US/Pacific")

    # Create plot
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Plot Temperature
    ax1.set_xlabel("Time (Hour)")
    ax1.set_ylabel("Temperature (°C)", color="tab:red")
    ax1.plot(
        plotDf["start_times"],
        plotDf["hourly_temp"],
        color="tab:red",
        marker="o")
    ax1.tick_params(axis="y", labelcolor="tab:red")
    ax1.set_ylim(40, 80)

    # Format x-axis to show every hour
    ax1.xaxis.set_major_locator(
        mdates.HourLocator(
            interval=1))  # Set ticks every hour
    ax1.xaxis.set_major_formatter(
        mdates.DateFormatter("%H", tz="US/Pacific")
    )  # Show only hours
    plt.xticks(rotation=45)  # Rotate labels for readability
    # Set ticks every 5 degrees
    ax1.yaxis.set_major_locator(ticker.MultipleLocator(5))
    ax1.grid(
        True,
        which="major",
        axis="y",
        linestyle="--",
        linewidth=0.5,
        color="gray")
    # Add gridlines at every hour
    ax1.grid(
        True,
        which="major",
        axis="x",
        linestyle="--",
        linewidth=0.5,
        color="gray")
    # Create Precipitation axis
    ax2 = ax1.twinx()
    ax2.set_ylabel("Precipitation (in)", color="tab:blue")
    ax2.plot(
        plotDf["start_times"],
        plotDf["hourly_qpf"],
        color="tab:blue",
        marker="o")
    ax2.tick_params(axis="y", labelcolor="tab:blue")
    ax2.set_ylim(0, 0.15)

    plt.tight_layout()
    plt.savefig("temp.png")
    plt.show()


def getTodayString():
    today = datetime.datetime.today()
    formatted_date = today.strftime("%A, %m-%d-%Y")
    return formatted_date


def writeEmailMessage(plotDf):
    max_temp = plotDf.iloc[plotDf["hourly_temp"].idxmax()]
    total_rain = plotDf["hourly_qpf"].sum()
    formatted_date = getTodayString()

    message = f"<p>====== Weather for {formatted_date} ======<p>A high of {
        int(
            max_temp.hourly_temp)}F at {
        max_temp.start_times.strftime("%H")}:00."

    if total_rain > 0:
        message += f"<p>{total_rain} total inches of rain are forecasted to fall toady."
    else:
        message += "<p>No rain forecasted today."

    return message


def sendMessage(plotDf):
    message = writeEmailMessage(plotDf)
    formattedDate = getTodayString()
    subject = f"Weather for {formattedDate}"
    body = message
    recipients = [TARGET_EMAIL]

    hw = historicalWeather.HistoricWeatherRetriever(datetime.datetime.now())
    hw.runJob()
    historical_weather_report = hw.printWeatherReport()

    html_body = f"""
    <html>
    <body>
        <div>{body}</div>
        <img src="cid:image1" />
        <div>{historical_weather_report}</div>
    </body>
    </html>
    """

    es = EmailSender(SENDER_EMAIL, SENDER_PASS, recipients)
    es.sendMessage(subject=subject, body=html_body)
    
class EmailSender():
    def __init__(self, senderEmail: str, senderPass: str, recieverEmail: list[str]):
        self.senderEmail = senderEmail
        self.senderPass = senderPass
        self.recieverEmail = recieverEmail

    def sendMessage(self, subject:str, body: str, image_file_name: str = None):
        msg = MIMEMultipart()
        msg.attach(MIMEText(body, "html"))
        if image_file_name:
            # Attach the image
            image_path = "temp.png"  # Path to the image you want to include
            with open(image_path, "rb") as img_file:
                img = MIMEImage(img_file.read())
                # This is the reference in the HTML
                img.add_header("Content-ID", "<image1>")
                msg.attach(img)
        msg["Subject"] = subject
        msg["From"] = self.senderEmail
        msg["To"] = ", ".join(self.recieverEmail)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp_server:
            smtp_server.login(self.senderEmail, self.recieverEmail)
            smtp_server.sendmail(self.senderEmail, self.recieverEmail, msg.as_string())

def main():
    bsData = requestData()
    df = processData(bsData=bsData)
    st = getStartDateTime()
    et = getEndDateTime()
    plotDf = getPlotDF(df, st, et)
    plot(plotDf)
    sendMessage(plotDf)


main()
