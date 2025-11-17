import sunspec2.modbus.client as client

d = client.SunSpecModbusClientDeviceTCP(slave_id=126, ipaddr="192.168.1.170", ipport=502)
d.scan()

d.controls[0].WMaxLimPct.value = 10000
d.controls[0].WMaxLimPct.write()
d.controls[0].read()
print(d.controls[0].WMaxLimPct.value)

