


import com.aspose.words.*;



public class GenerateTOC {
    public static void main(String[] args) throws Exception {
        // Set font directory to avoid invalid font errors
        FontSettings.getDefaultInstance().setFontsFolder("/data/data/com.termux/files/home/fonts", true);

        // Load original document (unchanged)
        Document originalDoc = new Document("input.docx");

        // Create a new document for the TOC
        Document tocDoc = new Document();
        DocumentBuilder builder = new DocumentBuilder(tocDoc);
        builder.writeln("Table of Contents");
        builder.getParagraphFormat().setStyleIdentifier(StyleIdentifier.HEADING_1);
        builder.insertTableOfContents("\\o \"1-3\" \\h \\z \\u");
        tocDoc.updateFields(); // Update TOC based on headings

        // Copy original content to new document
        for (Section section : originalDoc.getSections()) {
            tocDoc.getLastSection().getBody().appendChild(section.getBody().deepClone(true));
        }

        // Save new document with TOC
        tocDoc.save("output_with_toc.docx");

        System.out.println("TOC generated in output_with_toc.docx without modifying input.docx");
    }
}
^O

^X




jobs
killall nano





nano GenerateTOC.java
# Create fonts directory
mkdir -p ~/fonts

# Download Lato
wget https://github.com/google/fonts/raw/main/ofl/lato/Lato-Regular.ttf -O ~/fonts/Lato-Regular.ttf

# Verify
ls ~/fonts
chmod 644 ~/fonts/*.ttf
cp /sdcard/Download/Arial.ttf ~/fonts/Arial.ttf
chmod 644 ~/fonts/Arial.ttf
ls ~/fonts
nano GenerateTOC.java
import com.aspose.words.*;

public class GenerateTOC {
    public static void main(String[] args) throws Exception {
        // Set font directory to avoid invalid font errors
        FontSettings.getDefaultInstance().setFontsFolder("/data/data/com.termux/files/home/fonts", true);

        // Load original document (unchanged)
        Document originalDoc = new Document("input.docx");

        // Create a new document for the TOC
        Document tocDoc = new Document();
        DocumentBuilder builder = new DocumentBuilder(tocDoc);
        builder.writeln("Table of Contents");
        builder.getParagraphFormat().setStyleIdentifier(StyleIdentifier.HEADING_1);
        builder.insertTableOfContents("\\o \"1-3\" \\h \\z \\u");
        tocDoc.updateFields(); // Update TOC based on headings

        // Copy original content
        for (Section section : originalDoc.getSections()) {
            tocDoc.getLastSection().getBody().appendChild(section.getBody().deepClone(true));
        }

        // Save new document with TOC
        tocDoc.save("output_with_toc.docx");

        System.out.println("TOC generated in output_with_toc.docx without modifying input.docx");
    }
}
pkg install openjdk-17
java -version
pkg install openjdk-17
java -version
cp /sdcard/Download/aspose-words.jar .
javac -cp aspose-words.jar GenerateTOC.java
java -cp .:aspose-words.jar GenerateTOC





cp ~/fonts/*.ttf /data/data/<your.app.package>/files/fonts/ 
logcat | grep -i font
pkg install pdftk
pdftk input.pdf dump_data output toc.txt
echo "Table of Contents" > toc_page.txt
cat toc.txt >> toc_page.txt
pkg install enscript
enscript -o toc_page.pdf toc_page.txt
pdftk toc_page.pdf input.pdf output output_with_toc.pdf

pkg install python
pip install PyPDF2
from PyPDF2 import PdfReader, PdfWriter

reader = PdfReader("input.pdf")
writer = PdfWriter()
toc_page = writer.add_page()
for i in range(len(reader.pages)):
    writer.add_page(reader.pages[i])
with open("output_with_toc.pdf", "wb") as f:
    writer.write(f)
wget https://github.com/google/fonts/raw/main/ofl/lato/Lato-Regular.ttf -O ~/fonts/Lato-Regular.ttf
chmod 644 ~/fonts/*.ttf
ls ~/fonts







