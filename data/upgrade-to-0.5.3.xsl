<?xml version='1.0'?>
<!DOCTYPE xsl:stylesheet
[
]>
<xsl:stylesheet
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  version="1.0">

<!-- this stylesheet upgrades configuration files from Flumotion < 0.5.3 -->
<xsl:output method="xml" indent="yes" />

  <!-- fix up component version -->
  <xsl:template match="//planet/*/component/@version">
    <xsl:attribute name="version">0.5.3</xsl:attribute>
  </xsl:template>

  <!-- fix up plug socket strings for both manager and components -->
  <xsl:template match="//planet//plugs/plug/@socket">
    <xsl:attribute name="socket">
      <xsl:choose>
        <xsl:when test=". = 'flumotion.component.plugs.adminaction.AdminAction'"
          >flumotion.component.plugs.adminaction.AdminActionPlug</xsl:when>
        <xsl:when test=". = 'flumotion.component.plugs.lifecycle.ComponentLifecycle'"
          >flumotion.component.plugs.base.ComponentPlug</xsl:when>
        <xsl:when test=". = 'flumotion.component.plugs.identity.IdentityProvider'"
          >flumotion.component.plugs.identity.IdentityProviderPlug</xsl:when>
        <xsl:when test=". = 'flumotion.component.plugs.lifecycle.ManagerLifecycle'"
          >flumotion.component.plugs.base.ManagerPlug</xsl:when>
        <xsl:when test=". = 'flumotion.component.misc.httpserver.ratecontrol.RateController'"
          >flumotion.component.misc.httpserver.ratecontrol.RateControllerPlug</xsl:when>
        <xsl:otherwise>
          <xsl:value-of select="." />
        </xsl:otherwise>
      </xsl:choose>
    </xsl:attribute>
  </xsl:template>

  <!-- fix up plug type strings -->
  <xsl:template match="//planet/*/component/plugs/plug/@type">
    <xsl:attribute name="type">
      <xsl:choose>
        <!-- adminaction -->
        <xsl:when test=". = 'adminactionfilelogger'"
          >adminaction-loggerfile</xsl:when>
        <!-- bouncer -->
        <xsl:when test=". = 'token-test-bouncer-plug'"
          >bouncer-testtoken</xsl:when>
        <xsl:when test=". = 'trivial-bouncer-plug'"
          >bouncer-trivial</xsl:when>
        <!-- component -->
        <xsl:when test=". = 'componentlifecycleprinter'"
          >component-example</xsl:when>
        <xsl:when test=". = 'cortado-plug'"
          >component-cortado</xsl:when>
        <!-- identityprovider -->
        <xsl:when test=". = 'exampleidentityprovider'"
          >identityprovider-example</xsl:when>
        <!-- manager -->
        <xsl:when test=". = 'managerlifecycleprinter'"
          >manager-example</xsl:when>
        <xsl:when test=". = 'manager-manhole-plug'"
          >manager-manhole</xsl:when>
        <!-- ratecontroller -->
        <xsl:when test=". = 'fixed-rate-plug'"
          >ratecontroller-fixed</xsl:when>
        <!-- requestlogger -->
        <xsl:when test=". = 'apachelogger'"
          >requestlogger-file</xsl:when>
        <!-- streamdataprovider -->
        <xsl:when test=". = 'examplestreamdataprovider'"
          >streamdataprovider-example</xsl:when>
        <xsl:otherwise>
          <xsl:value-of select="." />
        </xsl:otherwise>
      </xsl:choose>
    </xsl:attribute>
  </xsl:template>

  <!-- Copy all the other nodes -->
  <xsl:template match="@*|node()">
    <xsl:copy>
      <xsl:apply-templates select="@*|node()"/>
    </xsl:copy>
  </xsl:template>

</xsl:stylesheet>
