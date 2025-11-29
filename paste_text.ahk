#Requires AutoHotkey v2.0
#SingleInstance Force

; Быстрый режим отправки
A_SendMode := "Input"
SetKeyDelay -1

Sleep 150  ; небольшая задержка для стабильности

text := A_Clipboard  ; содержимое буфера обмена

if (Type(text) = "String" && text != "")
{
    ; В буфере есть текст – вставляем его как набор символов
    ; Это не зависит от раскладки и VK-кодов
    SendText text
}
else
{
    ; В буфере НЕ текст (картинка, форматированный объект и т.п.)
    ; Пытаемся вставить через стандартное сообщение WM_PASTE (0x0302)
    ; в активный контрол
    PostMessage(0x0302, 0, 0, , "A")  ; WM_PASTE активному окну
}

Sleep 50
ExitApp
