# keyboard forward

- 硬件：xiao nrf52840
- 固件： CircuitPython 10.2

## 产品目标

将电脑的鼠标键盘通过单片机蓝牙转发到另外一个设备

## 单片机程序

- 自身是一个BLE HID设备
    - 其中鼠标设备使用 https://github.com/neradoc/circuitpython_absolute_mouse
        - 库已经安装
- 通过串口通信，接受鼠标与键盘指令数据。
- 串口通信同样控制开始配对的时机
    - 并把配对信息返回给串口
- 将指令转换为实际hid操作发送给配对的 master devise

## 上位机程序

- single file html page
- 使用 web serial 与单片机通信
- UI
    - 设置区
    - 鼠标镜像区

设置
- 配对按键
- 配对状态
- 鼠标区逻辑像素数目 [横]x[竖]
- 鼠标区横向UI大小

逻辑
- 上位机程序与单片机链接
- 鼠标区的逻辑像素数目应与HID的目标设备一致
- 当光标在该区域上移动时，通过ui大小和逻辑像素数目计算出目标设备的对应位置。
- 然后发送 absolute mouse position 到串口。
- 当光标在该区域内时，鼠标的点击，滚动和键盘操作被网页捕获，并发送给串口。