/*
  Arduino UNO R4 Minima
  IR Spectroscope MUX Controller

  Purpose:
  - Identify the Arduino over USB serial.
  - Route configured MUX inputs to MUX Output A, Output B, and Output EXT.
  - Report latched route state for hardware logs.
  - Provide a safe state that disables all MUX boards.

  Serial settings:
  - Baud: 115200
  - Line ending: Newline or Both NL & CR

  This firmware does not generate waveforms or simulated device data.
*/

const char* DEVICE_NAME = "ARDUINO_MUX_V1";
const char* FIRMWARE_VERSION = "0.1.0";
const char* DEVICE_ROLE = "mux_controller";
const char* PROTOCOL_VERSION = "MUX_ROUTE_PROTOCOL_1";

const int LED_PIN = LED_BUILTIN;

// Most 16-channel analog/digital mux boards use active-low EN pins.
// Verify the installed boards before changing this constant.
const bool MUX_ENABLE_ACTIVE_LOW = true;

const int DMB1_EN = 2;   // MUX Output A digital board
const int DMB2_EN = 3;   // MUX Output B digital board
const int AMB1_EN = 4;   // MUX Output A analog board
const int AMB2_EN = 5;   // MUX Output B analog board
const int DMB3_EN = A0;  // MUX Output EXT digital board

const int CH_A_SELECT_PINS[4] = {6, 7, 8, 9};
const int CH_B_SELECT_PINS[4] = {10, 11, 12, 13};
const int EXT_SELECT_PINS[4] = {A1, A2, A3, A4};

String inputBuffer = "";
String latchedRouteA = "DISABLED";
String latchedRouteB = "DISABLED";
String latchedRouteExt = "DISABLED";

struct RouteDef
{
  const char* name;
  const char* target;
  const char* board;
  byte channel;
};

const RouteDef ROUTES[] = {
  {"DMB1_C0_HF2LI_DIO9", "A", "DMB1", 0},
  {"DMB1_C1_HF2LI_DIO10", "A", "DMB1", 1},
  {"DMB1_C2_HF2LI_DIO11", "A", "DMB1", 2},
  {"DMB1_C3_HF2LI_DIO12", "A", "DMB1", 3},
  {"DMB1_C4_HF2LI_DIO13", "A", "DMB1", 4},
  {"DMB1_C5_HF2LI_DIO14", "A", "DMB1", 5},
  {"DMB1_C6_HF2LI_DIO15", "A", "DMB1", 6},

  {"DMB2_C0_HF2LI_DIO9", "B", "DMB2", 0},
  {"DMB2_C1_HF2LI_DIO10", "B", "DMB2", 1},
  {"DMB2_C2_HF2LI_DIO11", "B", "DMB2", 2},
  {"DMB2_C3_HF2LI_DIO12", "B", "DMB2", 3},
  {"DMB2_C4_HF2LI_DIO13", "B", "DMB2", 4},
  {"DMB2_C5_HF2LI_DIO14", "B", "DMB2", 5},
  {"DMB2_C6_HF2LI_DIO15", "B", "DMB2", 6},

  {"DMB3_C0_HF2LI_DIO9", "EXT", "DMB3", 0},
  {"DMB3_C1_HF2LI_DIO10", "EXT", "DMB3", 1},
  {"DMB3_C2_HF2LI_DIO11", "EXT", "DMB3", 2},
  {"DMB3_C3_HF2LI_DIO12", "EXT", "DMB3", 3},
  {"DMB3_C4_HF2LI_DIO13", "EXT", "DMB3", 4},
  {"DMB3_C5_HF2LI_DIO14", "EXT", "DMB3", 5},
  {"DMB3_C6_HF2LI_DIO15", "EXT", "DMB3", 6},

  {"AMB1_C0_HF2LI_AUX1", "A", "AMB1", 0},
  {"AMB1_C1_HF2LI_AUX2", "A", "AMB1", 1},
  {"AMB1_C2_HF2LI_AUX3", "A", "AMB1", 2},
  {"AMB1_C3_HF2LI_AUX4", "A", "AMB1", 3},

  {"AMB2_C0_HF2LI_AUX1", "B", "AMB2", 0},
  {"AMB2_C1_HF2LI_AUX2", "B", "AMB2", 1},
  {"AMB2_C2_HF2LI_AUX3", "B", "AMB2", 2},
  {"AMB2_C3_HF2LI_AUX4", "B", "AMB2", 3}
};

const int ROUTE_COUNT = sizeof(ROUTES) / sizeof(ROUTES[0]);

void setup()
{
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  configureMuxPins();
  safeDisableAllMuxes();

  Serial.begin(115200);
  delay(1000);

  Serial.println("ARDUINO_MUX_BOOT");
  Serial.println("READY");
}

void loop()
{
  handleSerialCommands();
  heartbeat();
}

void configureMuxPins()
{
  pinMode(DMB1_EN, OUTPUT);
  pinMode(DMB2_EN, OUTPUT);
  pinMode(AMB1_EN, OUTPUT);
  pinMode(AMB2_EN, OUTPUT);
  pinMode(DMB3_EN, OUTPUT);

  for (int i = 0; i < 4; i++)
  {
    pinMode(CH_A_SELECT_PINS[i], OUTPUT);
    pinMode(CH_B_SELECT_PINS[i], OUTPUT);
    pinMode(EXT_SELECT_PINS[i], OUTPUT);
    digitalWrite(CH_A_SELECT_PINS[i], LOW);
    digitalWrite(CH_B_SELECT_PINS[i], LOW);
    digitalWrite(EXT_SELECT_PINS[i], LOW);
  }
}

void handleSerialCommands()
{
  while (Serial.available() > 0)
  {
    char c = Serial.read();

    if (c == '\n' || c == '\r')
    {
      inputBuffer.trim();

      if (inputBuffer.length() > 0)
      {
        processCommand(inputBuffer);
      }

      inputBuffer = "";
    }
    else
    {
      inputBuffer += c;
    }
  }
}

void processCommand(String cmd)
{
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "WHOAMI")
  {
    Serial.println(DEVICE_NAME);
  }
  else if (cmd == "VERSION")
  {
    Serial.println(FIRMWARE_VERSION);
  }
  else if (cmd == "PROTOCOL")
  {
    Serial.println(PROTOCOL_VERSION);
  }
  else if (cmd == "STATUS")
  {
    printStatus();
  }
  else if (cmd == "ROLE")
  {
    Serial.println(DEVICE_ROLE);
  }
  else if (cmd == "PING")
  {
    Serial.println("PONG");
  }
  else if (cmd == "ROUTES?" || cmd == "ROUTE?")
  {
    printRoutes();
  }
  else if (cmd == "SAFE" || cmd == "DISABLE")
  {
    safeDisableAllMuxes();
    Serial.println("OK SAFE");
  }
  else if (cmd == "PINS?")
  {
    printPins();
  }
  else if (cmd == "HELP")
  {
    printHelp();
  }
  else if (cmd == "RESET")
  {
    Serial.println("RESETTING");
    delay(100);
    NVIC_SystemReset();
  }
  else if (cmd.startsWith("ROUTE "))
  {
    handleRouteCommand(cmd);
  }
  else
  {
    Serial.print("ERROR UNKNOWN_COMMAND ");
    Serial.println(cmd);
  }
}

void handleRouteCommand(String cmd)
{
  int firstSpace = cmd.indexOf(' ');
  int secondSpace = cmd.indexOf(' ', firstSpace + 1);

  if (secondSpace < 0)
  {
    Serial.println("ERROR ROUTE_USAGE ROUTE <A|B|EXT> <ROUTE_NAME>");
    return;
  }

  String target = cmd.substring(firstSpace + 1, secondSpace);
  String routeName = cmd.substring(secondSpace + 1);
  target.trim();
  routeName.trim();

  if (!(target == "A" || target == "B" || target == "EXT"))
  {
    Serial.print("ERROR UNKNOWN_TARGET ");
    Serial.println(target);
    return;
  }

  const RouteDef* route = findRoute(routeName);
  if (route == nullptr)
  {
    Serial.print("ERROR UNKNOWN_ROUTE ");
    Serial.println(routeName);
    return;
  }

  if (target != route->target)
  {
    Serial.print("ERROR ROUTE_TARGET_MISMATCH ");
    Serial.print(target);
    Serial.print(" ");
    Serial.println(routeName);
    return;
  }

  applyRoute(*route);
  Serial.print("OK ROUTE ");
  Serial.print(target);
  Serial.print(" ");
  Serial.println(routeName);
}

const RouteDef* findRoute(String routeName)
{
  for (int i = 0; i < ROUTE_COUNT; i++)
  {
    if (routeName == ROUTES[i].name)
    {
      return &ROUTES[i];
    }
  }

  return nullptr;
}

void applyRoute(const RouteDef& route)
{
  if (String(route.target) == "A")
  {
    setEnable(DMB1_EN, false);
    setEnable(AMB1_EN, false);
    setSelectBus(CH_A_SELECT_PINS, route.channel);

    if (String(route.board) == "DMB1")
    {
      setEnable(DMB1_EN, true);
    }
    else
    {
      setEnable(AMB1_EN, true);
    }

    latchedRouteA = route.name;
  }
  else if (String(route.target) == "B")
  {
    setEnable(DMB2_EN, false);
    setEnable(AMB2_EN, false);
    setSelectBus(CH_B_SELECT_PINS, route.channel);

    if (String(route.board) == "DMB2")
    {
      setEnable(DMB2_EN, true);
    }
    else
    {
      setEnable(AMB2_EN, true);
    }

    latchedRouteB = route.name;
  }
  else if (String(route.target) == "EXT")
  {
    setEnable(DMB3_EN, false);
    setSelectBus(EXT_SELECT_PINS, route.channel);
    setEnable(DMB3_EN, true);
    latchedRouteExt = route.name;
  }
}

void setSelectBus(const int pins[4], byte channel)
{
  for (int bitIndex = 0; bitIndex < 4; bitIndex++)
  {
    digitalWrite(pins[bitIndex], (channel >> bitIndex) & 0x01);
  }
}

void setEnable(int pin, bool enabled)
{
  if (MUX_ENABLE_ACTIVE_LOW)
  {
    digitalWrite(pin, enabled ? LOW : HIGH);
  }
  else
  {
    digitalWrite(pin, enabled ? HIGH : LOW);
  }
}

void safeDisableAllMuxes()
{
  setEnable(DMB1_EN, false);
  setEnable(DMB2_EN, false);
  setEnable(AMB1_EN, false);
  setEnable(AMB2_EN, false);
  setEnable(DMB3_EN, false);

  latchedRouteA = "DISABLED";
  latchedRouteB = "DISABLED";
  latchedRouteExt = "DISABLED";
}

void printStatus()
{
  Serial.print("READY ");
  printRoutesInline();
}

void printRoutes()
{
  Serial.print("ROUTES ");
  printRoutesInline();
}

void printRoutesInline()
{
  Serial.print("A=");
  Serial.print(latchedRouteA);
  Serial.print(" B=");
  Serial.print(latchedRouteB);
  Serial.print(" EXT=");
  Serial.println(latchedRouteExt);
}

void printPins()
{
  Serial.println("PINS DMB1_EN=D2 DMB2_EN=D3 AMB1_EN=D4 AMB2_EN=D5 DMB3_EN=A0");
  Serial.println("PINS A_BUS_S0=D6 A_BUS_S1=D7 A_BUS_S2=D8 A_BUS_S3=D9");
  Serial.println("PINS B_BUS_S0=D10 B_BUS_S1=D11 B_BUS_S2=D12 B_BUS_S3=D13");
  Serial.println("PINS EXT_BUS_S0=A1 EXT_BUS_S1=A2 EXT_BUS_S2=A3 EXT_BUS_S3=A4");
}

void printHelp()
{
  Serial.println("AVAILABLE_COMMANDS:");
  Serial.println("WHOAMI     -> ARDUINO_MUX_V1");
  Serial.println("VERSION    -> firmware version");
  Serial.println("PROTOCOL   -> route protocol version");
  Serial.println("STATUS     -> READY plus latched routes");
  Serial.println("ROLE       -> mux_controller");
  Serial.println("PING       -> PONG");
  Serial.println("ROUTE A <ROUTE_NAME>");
  Serial.println("ROUTE B <ROUTE_NAME>");
  Serial.println("ROUTE EXT <ROUTE_NAME>");
  Serial.println("ROUTES?    -> latched routes");
  Serial.println("SAFE       -> disable all mux boards");
  Serial.println("PINS?      -> pin topology");
  Serial.println("RESET      -> reset Arduino");
  Serial.println("HELP       -> command list");
}

void heartbeat()
{
  static unsigned long lastToggle = 0;
  static bool ledState = false;

  unsigned long now = millis();

  if (now - lastToggle >= 1000)
  {
    ledState = !ledState;
    digitalWrite(LED_PIN, ledState);
    lastToggle = now;
  }
}
