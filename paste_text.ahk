#Requires AutoHotkey v2.0
#SingleInstance Force ; Автоматически заменять предыдущий экземпляр скрипта без диалогового окна.

; Устанавливаем самый быстрый и надежный режим отправки ввода.
A_SendMode := "Input"
SetKeyDelay -1

; Задержка для стабильности
Sleep 200

; Определяем текущую раскладку клавиатуры
currentLayout := WinGetKeyboardLayout("A") & 0xFFFF

; Вставка в зависимости от раскладки
if (currentLayout = 1049) {
    ; Русская раскладка - вставляем через Ctrl+V
    Send("^v")
} else {
    ; Все остальные раскладки - вставляем через Ctrl+M
    Send("^m")
}

Sleep 100

ExitApp

/**
 * Возвращает идентификатор раскладки клавиатуры для указанного окна.
 * @param winTitle Идентификатор окна (по умолчанию "A" - активное окно).
 * @returns {Integer} ID раскладки.
 */
WinGetKeyboardLayout(winTitle := "A") {
    try
    {
        threadId := DllCall("GetWindowThreadProcessId", "Ptr", WinExist(winTitle), "Ptr", 0)
        info := DllCall("GetKeyboardLayout", "UInt", threadId, "Ptr")
        Return info
    }
    catch
    {
        Return 0 ; В случае ошибки возвращаем нейтральное значение
    }
}
