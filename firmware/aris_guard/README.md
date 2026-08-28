# ARIS Guard firmware

Firmware Arduino UNO cho prototype sonar và điều khiển hồng ngoại của ARIS.

## Wiring

| Component | Arduino UNO |
| --- | --- |
| HC-SR04 VCC | 5V |
| HC-SR04 GND | GND |
| HC-SR04 TRIG | D9 |
| HC-SR04 ECHO | D10 |
| IR G | GND |
| IR R | 3.3V |
| IR Y | D2 |

Ngắt USB trước khi thay đổi dây. Tất cả GND phải nối chung.

## Verified remote commands

| Button | NEC command |
| --- | --- |
| POWER | `0x45` |
| OK | `0x40` |
| 0 | `0x16` |
| BACK | `0x44` |

`POWER` bắt đầu đếm ngược 10 giây. `OK`, `BACK`, hoặc `0` đưa hệ thống về
`OFF`. `0` được giữ làm nút dừng khẩn cấp.

## Serial protocol

Baud rate: `115200`.

Python chỉ gửi một trong bốn dòng allowlist: `ARM`, `DISARM`, `STOP`, hoặc
`STATUS`. Firmware phát sự kiện có tiền tố `ARIS_HW|`, ví dụ
`ARIS_HW|STATE|ALERT`. Không có câu lệnh tùy ý nào được thực thi.
