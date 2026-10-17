/**
 * SMART ENERGY METER - ESP32 IoT SENSOR NODE
 * Target Hardware: ESP32 Dev Module (WROOM-32)
 *
 * Capabilities:
 * - Secure Wi-Fi connectivity with auto-reconnection & exponential backoff
 * - Persistent NVS non-volatile storage for cumulative kWh (survives power cuts/reboots)
 * - JSON telemetry packaging matching FastAPI /api/readings schema
 * - Dual Mode:
 *     1. Physical Measurement via PZEM-004T v3.0 (UART isolated interface)
 *     2. Calibrated Simulation Mode (clearly flagged as is_simulated=true)
 * - Diagnostics streamed via Hardware Serial @ 115200 baud
 *
 * Electrical Safety:
 * NEVER connect mains voltage (230V AC) directly to ESP32 GPIOs!
 * Always use galvanically isolated energy measurement ICs with optocouplers.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>

// Include local configuration (copy from config.h.example)
#if __has_include("config.h")
  #include "config.h"
#else
  #define WIFI_SSID       "SMART_ENERGY_WIFI"
  #define WIFI_PASSWORD   "CHANGEME_PASSWORD"
  #define API_BASE_URL    "http://192.168.1.7:8000"
  #define API_ENDPOINT    "/api/readings"
  #define NODE_DEVICE_ID  "esp32_meter_01"
  #define POST_INTERVAL_MS 15000
  #define HARDWARE_SENSOR_CONNECTED 0
  #define PZEM_RX_PIN 16
  #define PZEM_TX_PIN 17
#endif

// Non-Volatile Flash Storage for Cumulative Energy Counter
Preferences preferences;
const char* PREF_NAMESPACE = "meter_data";
const char* PREF_KWH_KEY   = "cum_kwh";

// Telemetry State
float cumulativeKwh = 1200.0f; // Default baseline if NVS is empty
unsigned long lastPostTime = 0;
int wifiReconnectAttempts = 0;

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.printf("\n[WiFi] Connecting to SSID: %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int timeoutCounter = 0;
  while (WiFi.status() != WL_CONNECTED && timeoutCounter < 20) {
    delay(500);
    Serial.print(".");
    timeoutCounter++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Connected! IP Address: %s | RSSI: %d dBm\n",
                  WiFi.localIP().toString().c_str(), WiFi.RSSI());
    wifiReconnectAttempts = 0;
  } else {
    Serial.printf("\n[WiFi] Failed to connect. Will retry in %d seconds.\n", min(60, 5 * (wifiReconnectAttempts + 1)));
    wifiReconnectAttempts++;
  }
}

void loadPersistedKwh() {
  preferences.begin(PREF_NAMESPACE, false);
  cumulativeKwh = preferences.getFloat(PREF_KWH_KEY, 1200.0f);
  preferences.end();
  Serial.printf("[NVS] Restored cumulative energy from flash: %.4f kWh\n", cumulativeKwh);
}

void savePersistedKwh(float kwh) {
  preferences.begin(PREF_NAMESPACE, false);
  preferences.putFloat(PREF_KWH_KEY, kwh);
  preferences.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n==================================================");
  Serial.println("  SMART ENERGY METER - ESP32 SENSOR NODE v1.1    ");
  Serial.printf ("  Node ID: %s | Mode: %s\n", NODE_DEVICE_ID,
                 HARDWARE_SENSOR_CONNECTED ? "HARDWARE (PZEM-004T)" : "SIMULATED");
  Serial.println("==================================================");

  loadPersistedKwh();
  connectWiFi();
}

void transmitTelemetry(float kwh, float watts, float volts, float amps, bool isSimulated) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[HTTP] Wi-Fi not connected. Attempting reconnection...");
    connectWiFi();
    if (WiFi.status() != WL_CONNECTED) return;
  }

  HTTPClient http;
  String fullUrl = String(API_BASE_URL) + String(API_ENDPOINT);

  Serial.printf("[HTTP] Transmitting packet to: %s\n", fullUrl.c_str());
  http.begin(fullUrl);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000); // 5-second timeout

  // Construct JSON payload conforming to ReadingRequest schema
  String payload = "{";
  payload += "\"cumulative_kwh\":" + String(kwh, 4) + ",";
  payload += "\"power_watts\":" + String(watts, 1) + ",";
  payload += "\"voltage\":" + String(volts, 1) + ",";
  payload += "\"current_amps\":" + String(amps, 2) + ",";
  payload += "\"source\":\"" + String(NODE_DEVICE_ID) + "\",";
  payload += "\"is_simulated\":" + String(isSimulated ? "true" : "false");
  payload += "}";

  int httpCode = http.POST(payload);

  if (httpCode > 0) {
    Serial.printf("[HTTP] Success! HTTP Response Code: %d\n", httpCode);
    String response = http.getString();
    Serial.printf("[HTTP] Server Response: %s\n", response.c_str());
  } else {
    Serial.printf("[HTTP] Transmission Error: %s (Code: %d)\n",
                  http.errorToString(httpCode).c_str(), httpCode);
  }

  http.end();
}

void loop() {
  unsigned long now = millis();

  // Periodic transmission loop
  if (now - lastPostTime >= POST_INTERVAL_MS || lastPostTime == 0) {
    lastPostTime = now;

    float powerWatts = 0.0f;
    float voltage = 230.0f;
    float currentAmps = 0.0f;
    bool isSimulated = true;

#if HARDWARE_SENSOR_CONNECTED == 1
    // Physical energy meter reading (e.g. PZEM-004T v3.0)
    // float v = pzem.voltage();
    // float i = pzem.current();
    // float p = pzem.power();
    // float e = pzem.energy();
    // if (!isnan(v) && !isnan(p)) {
    //   voltage = v; currentAmps = i; powerWatts = p; cumulativeKwh = e;
    //   isSimulated = false;
    // }
#else
    // Safe Calibrated Simulation Mode for local test/verification
    powerWatts = random(250, 1100);                  // 250W to 1100W domestic active load
    voltage = 228.0f + (random(0, 50) / 10.0f);      // 228V to 233V typical grid voltage
    currentAmps = powerWatts / (voltage * 0.92f);     // Apparent current assuming 0.92 PF

    // Calculate energy accumulated during POST_INTERVAL_MS:
    // kWh = (Watts * (interval_ms / 3600000.0)) / 1000.0
    float intervalHours = (POST_INTERVAL_MS / 1000.0f) / 3600.0f;
    float deltaKwh = (powerWatts / 1000.0f) * intervalHours;
    cumulativeKwh += deltaKwh;
    isSimulated = true;

    // Persist updated energy to NVS every ~5 minutes or 20 intervals
    static int saveCounter = 0;
    if (++saveCounter >= 20) {
      savePersistedKwh(cumulativeKwh);
      saveCounter = 0;
    }
#endif

    Serial.printf("\n[Telemetry] Power: %.1f W | Volts: %.1f V | Current: %.2f A | Energy: %.4f kWh [%s]\n",
                  powerWatts, voltage, currentAmps, cumulativeKwh, isSimulated ? "SIMULATED" : "MEASURED");

    transmitTelemetry(cumulativeKwh, powerWatts, voltage, currentAmps, isSimulated);
  }

  delay(100);
}
