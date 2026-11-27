local file = assert(io.open(arg[1], 'rb'))
local size = assert(file:seek('end'))
local offset, start, buffer = 0, 0, ''

local function byte(limit)
    assert(offset < limit)
    if offset >= start + #buffer then
        start = offset
        assert(file:seek('set', start))
        buffer = assert(file:read(65536))
    end
    offset = offset + 1
    return buffer:byte(offset - start)
end

local function integer(limit)
    local value, scale = 0, 1
    for index = 1, 5 do
        local digit = byte(limit)
        assert(index < 5 or digit < 16)
        value = value + (digit % 128) * scale
        if digit < 128 then return value end
        scale = scale * 128
    end
    error('invalid protobuf length')
end

local function validate()
    local entries = false
    while offset < size do
        assert(integer(size) == 10)
        local length = integer(size)
        local boundary = offset + length
        assert(boundary <= size and integer(boundary) == 10)
        local code_length = integer(boundary)
        assert(code_length > 0 and code_length <= 255)
        for index = 1, code_length do
            local char = byte(boundary)
            assert(char >= 33 and char <= 126)
        end
        while offset < boundary do
            local tag = integer(boundary)
            if tag == 24 then
                assert(integer(boundary) <= 1)
            else
                assert(tag >= 18 and tag % 8 == 2)
                local payload = integer(boundary)
                if tag == 18 then
                    assert(payload > 0)
                    entries = true
                end
                offset = offset + payload
                assert(offset <= boundary)
            end
        end
    end
    assert(entries)
end

local valid = pcall(validate)
file:close()
os.exit(valid and 0 or 1)
