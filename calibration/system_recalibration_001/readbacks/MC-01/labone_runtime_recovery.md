# MC-01 LabOne runtime recovery

During repeat 2 DIO initialization, the legacy temporary path
`AppData/Local/Temp/zhinst_26_4` imported `zhinst.ziPython` as an incomplete
namespace without `ziDAQServer`. The failure occurred before T660 connection
or a process command; the waiting MIRcat process was stopped safely.

The same LabOne API family was reinstalled with Python 3.12 at the persistent
local runtime path:

`C:/Users/Chris/AppData/Local/Control_System/runtimes/zhinst_26_4_py312`

Verified read-only connection:

- LabOne API/package: `zhinst 26.4.0`, `zhinst.core 26.4.0.940`
- Device: `dev18500`
- Clockbase readback: `210000000 Hz`

Future MC-01 tasks shall use Python 3.12 and this persistent path and shall not
ask the operator to reinstall the already recovered runtime unless this
verification itself fails.
