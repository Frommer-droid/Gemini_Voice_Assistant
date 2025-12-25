#Requires AutoHotkey v2.0
#SingleInstance Force

SetTitleMatchMode 2
winTitle := "Everything ahk_class #32770"
logFile := A_ScriptDir "\everything_service_helper.log"

Log(msg) {
    global logFile
    FileAppend(FormatTime(A_Now, "yyyy-MM-dd HH:mm:ss") " " msg "`n", logFile, "UTF-8")
}

Log("Ожидаю окно: " winTitle)
if !WinWait(winTitle, , 20) {
    Log("Окно не найдено.")
    ExitApp
}

Log("Окно найдено. Отправляю клавиши.")
WinActivate(winTitle)
WinWaitActive(winTitle, , 3)
Sleep 150
Send "{Tab}{Down}{Enter}"
Log("Клавиши отправлены.")

ExitApp

ExitApp
