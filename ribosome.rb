#
# Copyright (c) 2014 Martin Sustrik  All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom
# the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#

################################################################################
#  DNA helper functions.                                                       #
################################################################################

# Print out the error and terminate the generation.
def dnaerror(s)
    $stderr.write("#{$dnafile}:#{$ln} - #{s}\n")
    exit()
end

# Remove whitespace from the beginning of the . or + line.
# Returns trimmed line and the amount of whitespace removed.
def ltrim(s)

    # Find out the amount of whitespace at the beginning of the line.
    ws = 0;
    for i in 1..s.size()
        if(s[i] == ?\s)
            ws += 1
            next
        end
        if(s[i] == ?\t)
            ws += 8
        end
        break
    end

    # Cut off the control character and any subsequent whitespace.
    s = s[i..-2]

    return ws,s
end


################################################################################
#  RNA helper functions.                                                       #
################################################################################

rnahelpers = '

module Ribosome

    def Ribosome.openroot(name)
        if(name[-4..-1] == ".xml")
            require "rexml/document"
            return REXML::Document.new(File.new(name)).root
        elsif(name[-5..-1] == ".json")
            require "rubygems"
            require "json"
            return JSON.parse(File.read(name))
        else
            $stderr.puts("input file must be either .json or .xml")
            exit()
        end
    end

    def Ribosome.write(s)
        $stack.last.push(s)
    end

    def Ribosome.close()
        for l in $stack.last
            $out.write(l)
        end
        $stack = [[]]
        $out.write("\n");
        if ($outisafile)
            $out.close()
        end
    end

    def Ribosome.expand(s, b)

        # Find all occurences of @{.
        i = -1
        while true
            i = s.index(\'@{\', i + 1)
            if(i == nil)
                break;
            end
            j = i + 1

            # Find corresponding }.
            par = 0;
            while true
                if(s[j] == ?{)
                    par += 1
                end
                if(s[j] == ?})
                    par -= 1
                end
                if(par == 0)
                    break
                end
                j += 1
            end

            # Replace the expression with its value.
            expr = s[i + 2..j - 1]
            $stack.push([])
            val = eval(expr, b)
            top = $stack.pop()
            if(top.empty?)

                # Classic functions.
                s[i..j] = val.to_s()
                i += val.to_s().size
            else

                # Ribosome functions.
                res = top.join()
                s[i..j] = res
                i += res.size
            end
            
        end

        return s
    end

    def Ribosome.adjust(line, ws)

        a = line.to_a()

        # Find top, bottom and left boundary of the block of text.
        i = 0
        top = -1
        bottom = -1
        left = -1
        for l in a
            if(!l.lstrip().empty?)
                if(top == -1)
                    top = i;
                end
                bottom = i;
                if (left == -1)
                    left = l.size() - l.lstrip().size()
                else
                    left = [left, l.size() - l.lstrip().size()].min
                end
            end
            i += 1
        end

        # Strip the top and bottom whitespace.
        if(top == -1)
            a = []
        else
            a = a[top..bottom]
        end

        # Strip the original whitespace from the left.
        # Add the amount of whitespace specified in the argument.
        for i in 0..a.size() - 1
            a[i] = " " * ws + a[i][left..-1]
        end

        # Return the adjusted block. Strip off the trailing newline.
        res = a.join
        if(res[-1] == ?\n)
            res = res[0..-2]
        end
        return res;

    end

    def Ribosome.dot(line, ws, bind)
        write("\n")
        write(adjust(expand(line, bind), ws))
    end

    def Ribosome.plus(line, bind)
        write(expand(line, bind))
    end

    # Initialise the ribosome stack. Each level on the stack contains a block of
    # text in the form of array of lines (strings).
    $stack = [[]]

    # Initialise output channel.
    $out = $stdout
    $outisafile = false

end

'

################################################################################
#  Main function.                                                              #
################################################################################

# Parse the command line arguments.
if(ARGV.size() != 1 && ARGV.size() != 2)
    puts("usage: ribosome <dna-file> [<input-file>]")
    exit()
end
$dnafile = ARGV[0]
if (ARGV.size < 2)
    infile = ""
else
    infile = ARGV[1]
end

# Open the files for the DNA-to-RNA translation step.
$ln = 0
if($dnafile[-4..-1] == ".dna")
    rnafile = $dnafile[0..-5] + ".rna.rb"
else
    rnafile = $dnafile + ".rna.rb"
end
dna = File.open($dnafile, "r")
rna = File.open(rnafile, "w")

# Add RNA helper functions.

rna.write(rnahelpers)

# Open the input file.
rna.write("if(ARGV.size > 0)\n")
rna.write("    $root = Ribosome.openroot(ARGV[0])\n")
rna.write("end\n\n")

# Process the DNA file, line-by-line.
while(line = dna.gets())

    # We are counting lines so that we can report line numbers in errors.
    $ln += 1

    # Empty lines are ignored.
    if(line.size() == 0 || line[0] == ?\n)
        next
    end

    # Lines starting with '!' are ribosome commands.
    if(line[0] == ?!)

        # Parse the arguments. This should probably be done in a more
        # sophisticated way in the future to allow arguments containing spaces.
        words = line[1..-1].split(/\s+/)

        # !separate is used to insert separators between
        # the iterations of a loop.
        #if(words[0] == 'separate') {
        #    rna.write("____first_#{$ln}____ = true\n")
        #    line = dna.gets()
        #    $ln += 1
        #    next
        #}

        # Remaining commands can be used only in the outermost scope.
        rna.write("if(Ribosome.$stack.size > 1)\n")
        rna.write("    $stderr.write(\"#{$dnafile}:#{$ln} - command '#{words[0]}' used in a nested function\\n\")\n")
        rna.write("    exit()\n")
        rna.write("end\n")

        # !output redirects the output to a different file.
        if(words[0] == 'output')
            if(words.size() != 2)
                dnaerror("command 'output' expects one argument")
            end
            rna.write("Ribosome.close()\n")
            rna.write("Ribosome.$outisafile = true\n")
            rna.write("Ribosome.$out = File.open(#{words[1]}, 'w')\n")
            next
        end

        # !stdout redirects the output to stdout.
        if(words[0] == 'stdout')
            if(words.size() != 1)
                dnaerror("command 'stdout' expects no arguments")
            end
            rna.write("Ribosome.close()\n")
            rna.write("Ribosome.$outisafile = false\n")
            rna.write("Ribosome.$out = $stdout\n")
            next
        end

        # Invalid command.
        $stderr.puts("#{$dnafile}:#{$ln} - invalid command '#{words[0]}'")
        exit()
    end

    # Dot indicates thar the following text should be copied to a new line
    # in the output. The text is properly indented.
    if(line[0] == ?.)
        ws,line = ltrim(line)
        rna.write("Ribosome.dot(#{line.inspect()}, #{ws}, binding)\n")
        next
    end

    # Plus sign (+) indicates that the following text should be copied to
    # the output without moving to a new line. No indenting kung-fu is done. 
    if(line[0] == ?+)
        ws,line = ltrim(line)
        rna.write("Ribosome.plus(#{line.inspect()}, binding)\n")
        next
    end

    # All other lines are copied to the RNA file verbatim.
    rna.write(line)

end

# Flush the output file.
rna.write("Ribosome.close()\n\n")

# Flush the RNA file.
rna.close()
dna.close()

# Execute the RNA file.
system("ruby #{rnafile} #{infile}")

# Delete the RNA file.
# For now we are letting the file be to help with debugging of ribosome.
# File.delete(rnafile)

