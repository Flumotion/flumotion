<?xml version='1.0'?>
<!DOCTYPE xsl:stylesheet
[
]>
<xsl:stylesheet
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  version="1.0">

<!-- this stylesheet upgrades configuration files from Flumotion < 0.2.0 -->
<xsl:output method="xml" indent="yes" />

<xsl:template match="/">
  <xsl:apply-templates />
</xsl:template>

<!-- match all element nodes -->
<xsl:template match="*">
  <!-- we want to copy this node's element and attributes -->
  <xsl:element name="{name()}">
    <!-- copy all attributes for this element node -->
    <xsl:for-each select="@*">
      <xsl:attribute name="{name()}"><xsl:value-of select="." /></xsl:attribute>
    </xsl:for-each>

  <!-- make sure we chain through to our component template -->
    <xsl:apply-templates />
  </xsl:element>

</xsl:template>

<!-- copy all comments -->
<xsl:template match="comment()">
<xsl:copy-of select="." />
</xsl:template>

<!-- transmogrify the component node -->
<!--
<xsl:template match="component" priority="2">
  COMPONENT
</xsl:template>
-->
<xsl:template match="component/*">
      <xsl:choose>
      <!-- we leave <source> alone -->
      <xsl:when test="name() = 'source'">
        <xsl:copy-of select="." />
      </xsl:when>
      <!-- we remove <feed> -->
      <xsl:when test="name() = 'feed'">
      </xsl:when>
      <xsl:otherwise>
        <xsl:element name="property">
          <xsl:attribute name="name"><xsl:value-of select="name()" /></xsl:attribute>
          <xsl:value-of select="." />
        </xsl:element>
      </xsl:otherwise>
      </xsl:choose>

</xsl:template>

</xsl:stylesheet>
