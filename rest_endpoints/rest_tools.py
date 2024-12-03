from fastapi import FastAPI, APIRouter, HTTPException, status
from pydantic import BaseModel
import subprocess
import platform
import re
import socket

app = FastAPI()
network_tools_router = APIRouter(
    prefix="/v1/api/tools",
    tags=["Network Tools"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Not found"}},
)

class IPAddress(BaseModel):
    ip: str

def get_source_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        source_ip = s.getsockname()[0]
        s.close()
    except Exception:
        source_ip = "Unable to determine source IP"
    return source_ip

def parse_ping_output(output: str):
    # Pattern for Linux/MacOS output
    packets_pattern_unix = re.compile(r"(\d+) packets transmitted, (\d+) received, (\d+)% packet loss")
    round_trip_pattern_unix = re.compile(r"min/avg/max/(?:mdev|stddev) = (\d+\.\d+)/(\d+\.\d+)/(\d+\.\d+)/\d+\.\d+ ms")

    # Pattern for Windows output
    packets_pattern_windows = re.compile(r"Sent = (\d+), Received = (\d+), Lost = (\d+) \((\d+)% loss\)")
    round_trip_pattern_windows = re.compile(r"Minimum = (\d+)ms, Maximum = (\d+)ms, Average = (\d+)ms")

    # Check Unix-like output
    packets_match = packets_pattern_unix.search(output)
    round_trip_match = round_trip_pattern_unix.search(output)

    if packets_match and round_trip_match:
        sent, received, loss = packets_match.groups()
        minimum, average, maximum = round_trip_match.groups()
    else:
        # Check Windows output if Unix patterns didn't match
        packets_match = packets_pattern_windows.search(output)
        round_trip_match = round_trip_pattern_windows.search(output)

        if packets_match and round_trip_match:
            sent, received, lost, loss = packets_match.groups()
            minimum, maximum, average = round_trip_match.groups()
        else:
            # If no patterns matched, return N/A values
            sent, received, loss = "N/A", "N/A", "N/A"
            minimum, average, maximum = "N/A", "N/A", "N/A"

    return f"Packets: Sent = {sent}, Received = {received}, Lost = {loss}%\n" \
           f"Minimum = {minimum} ms, Maximum = {maximum} ms, Average = {average} ms"

@network_tools_router.post("/ping")
async def ping_ip(address: IPAddress):
    ip = address.ip

    if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
        raise HTTPException(status_code=400, detail="Invalid IP address format")

    source_ip = get_source_ip()
    ping_command = ["ping", "-c", "4", ip] if platform.system() != "Windows" else ["ping", "-n", "4", ip]

    try:
        result = subprocess.run(ping_command, capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            parsed_message = parse_ping_output(result.stdout)
            return {
                "status": "success",
                "source_ip": source_ip,
                "destination_ip": ip,
                "message": parsed_message
            }
        else:
            return {
                "status": "error",
                "source_ip": source_ip,
                "destination_ip": ip,
                "message": result.stderr
            }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Ping request timed out")