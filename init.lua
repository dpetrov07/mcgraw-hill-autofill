-- Set this to true and reload Hammerspoon to print the payload and request timings.
local homeworkReviewDebug = false
local homeworkReviewWorker
local workerBuffer = ""
local workerBusy = false
local workerStopping = false
local requestStarted
local python = "/Users/danielpetrov/Documents/dev/automations/mcgraw-hill-autofill/.venv/bin/python"
local script = "/Users/danielpetrov/Documents/dev/automations/mcgraw-hill-autofill/homework_review.py"

local function handleWorkerLine(line)
    local ok, message = pcall(hs.json.decode, line)
    if not ok or type(message) ~= "table" then
        hs.alert.show("Homework Review — invalid worker response", 4)
        workerBusy = false
        return
    end
    if homeworkReviewDebug and message.payload then
        print("Homework Review payload: " .. hs.json.encode(message.payload, true))
        local t = message.timings
        print(string.format("Homework Review timing — request received: %.3fs", t.request_received))
        print(string.format("Homework Review timing — DOM extraction complete: %.3fs", t.dom_extraction_complete))
        if t.api_request_start then print(string.format("Homework Review timing — API request start: %.3fs", t.api_request_start)) end
        if t.api_response_received then print(string.format("Homework Review timing — API response received: %.3fs", t.api_response_received)) end
        print(string.format("Homework Review timing — answer returned to Hammerspoon: %.3fs", (hs.timer.absoluteTime() - requestStarted) / 1000000000))
    end
    if message.error then
        hs.alert.show("Homework Review — " .. message.error, 4)
    elseif homeworkReviewDebug and message.result then
        print("Homework Review result: " .. hs.json.encode(message.result, true))
        print("Homework Review application: " .. hs.json.encode(message.application, true))
    end
    workerBusy = false
end

local function readWorkerOutput(stdout)
    workerBuffer = workerBuffer .. stdout
    while true do
        local newline = workerBuffer:find("\n", 1, true)
        if not newline then return end
        local line = workerBuffer:sub(1, newline - 1)
        workerBuffer = workerBuffer:sub(newline + 1)
        if line ~= "" then handleWorkerLine(line) end
    end
end

local function startWorker()
    if homeworkReviewWorker and homeworkReviewWorker:isRunning() then return true end
    workerStopping = false
    workerBuffer = ""
    homeworkReviewWorker = hs.task.new(python, function(exitCode, _, stderr)
        homeworkReviewWorker = nil
        workerBusy = false
        if not workerStopping and exitCode ~= 0 then
            hs.alert.show("Homework Review worker stopped: " .. (stderr ~= "" and stderr or tostring(exitCode)), 4)
        end
    end, function(_, stdout, stderr)
        if stdout ~= "" then readWorkerOutput(stdout) end
        if homeworkReviewDebug and stderr ~= "" then print(stderr) end
        return true
    end, {script, "--worker"})
    return homeworkReviewWorker:start() ~= false
end

local function runHomeworkReview()
    if workerBusy then return end
    if not startWorker() then
        hs.alert.show("Homework Review worker could not start", 4)
        return
    end
    workerBusy = true
    requestStarted = hs.timer.absoluteTime()
    homeworkReviewWorker:setInput(hs.json.encode({
        browser = hs.application.frontmostApplication():name(),
        debug = homeworkReviewDebug,
    }) .. "\n")
end

startWorker()

hs.shutdownCallback = function()
    workerStopping = true
    if homeworkReviewWorker and homeworkReviewWorker:isRunning() then
        homeworkReviewWorker:terminate()
    end
end

hs.hotkey.bind({"alt"}, "q", function()
    runHomeworkReview()
end)
