<?xml version='1.0'?>
<!DOCTYPE xsl:stylesheet
[
]>
<xsl:stylesheet
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  version="1.0">

<!-- this stylesheet upgrades configuration files from Flumotion < 0.6.0 -->
<xsl:output method="xml" indent="yes" />

  <!-- fix up component version -->
  <xsl:template match="//planet/*/component/@version">
    <xsl:attribute name="version">0.6.0</xsl:attribute>
  </xsl:template>

  <!-- fix up deprecated <source> tags -->
  <xsl:template match="//planet/*/component/source">
    <eater name="default">
      <xsl:for-each select="../source">
        <feed><xsl:value-of select="."/></feed>
      </xsl:for-each>
    </eater>
  </xsl:template>

  <!-- Copy all the other nodes -->
  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
